import os
import re
import uuid
import base64
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

class GmailToolsClass:

    def __init__(self):
        self.service = self._get_email_service()

    def _get_email_service(self):
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json",SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credential.json",SCOPES)
                creds = flow.run_local_server(port = 0)
            with open("token.json","w") as token:
                token.write(creds.to_json())
            
        return build("gmail",'v1',credentials = creds)

    def fetch_recent_emails(self, max_results = 50):
        try:

            now = datetime.now()
            delay = now - timedelta(hours  = 8)

            after_timestamp = int(delay.timestamp())
            before_timestamp = int(now.timestamp())

            query = f"after:{after_timestamp} before:{before_timestamp}"

            results = self.service.users().messages().list(
                userId = "me", q= query, maxResults = max_results
            ).execute()
            

            messages = results.get("messages",[])

            return messages
        except Exception as error:
            print(f"An error occured while fetching emails: {error}")
            return []

    def _extract_main_content_from_html(self,html_content):

        soup = BeautifulSoup(html_content,"html.parser")
        for tag in soup(["script","style","head","meta","title"]):
            tag.decompose()

        return soup.get_text(separator = '\n', strip = True)

    def _get_email_body(self,payload):

        def decode_data(data):
            return base64.urlsafe_b64decode(data).decode('utf-8').strip() if data else ""
        
        def extract_body(parts):

            for part in parts:
                mime_type = part.get('mimeType','')
                data = part['body'].get('data','')

                if mime_type == 'text/plain':
                    return decode_data(data)
                if mime_type == 'text/html':
                    html_content = decode_data(data)
                    return self._extract_main_content_from_html(html_content)

                if 'parts' in part:
                    result = extract_body(part['parts'])
                    if result:
                        return result
            
            return ""

        if "parts" in payload:
            body = extract_body(payload["parts"])

        else:
            data = payload["body"].get("data",'')
            body = decode_data(data)
            if payload.get('mimeType') == 'text/html':
                body = self._extract_main_content_from_html(body)

        return self._clean_body_text(body)

    def _clean_body_text(self,text):

        return re.sub(r'\s+',' ',text.replace('\r','').replace('\n','')).strip()

    def _get_email_info(self,msg_id):
        message = self.service.users().messages().get(
            userId= "me", id = msg_id, format = "full"
        ).execute()

        payload = message.get('payload',{})
        headers = {header["name"].lower(): header["value"] for header in payload.get("headers",[])}

        return {
            "id": msg_id,
            "threadId": message.get("threadId"),
            "messageId": headers.get("message-id"),
            "references": headers.get("references",""),
            "sender": headers.get("from","Unknown"),
            "subject": headers.get("subject","No Subject"),
            "body": self._get_email_body(payload)
        }

    def _should_skip_email(self,email_info):
        return os.environ["MY_EMAIL"] in email_info["sender"]

    def fetch_unanswered_emails(self,max_results = 50):
        try:
            recent_emails = self.fetch_recent_emails(max_results)
            # print("Hiii")
            if not recent_emails: return []

            drafts = self.fetch_draft_replies()
            # print("hi")

            threads_with_drafts = {draft["threadId"] for draft in drafts}
            # print("hiii")
            seen_threads = set()
            unanswered_emails = []
            for email in recent_emails:
                # print("hii")
                thread_id = email["threadId"]
                if thread_id not in seen_threads and thread_id not in threads_with_drafts:
                    
                    seen_threads.add(thread_id)
                    email_info = self._get_email_info(email["id"])
                    # print("hiipython")
                    if self._should_skip_email(email_info):
                        continue
                    # print("hii")
                    unanswered_emails.append(email_info)
            return unanswered_emails

        except Exception as error:
            print(f"An error occured: {error}")
            return []

    def fetch_draft_replies(self):
        try:
            drafts  = self.service.users().drafts().list(userId = "me").execute()
            draft_list = drafts.get("drafts",[])

            return [       
                {
                    "draft_id": draft["id"],
                    "threadId":draft["message"]["threadId"],
                    "id": draft["message"]["id"],
                }
                for draft in draft_list
            ]
        except Exception as error:
            print(f"An error occured while fetching drafts {error}")
            return []

    def _create_html_email_message(self, recipient, subject, reply_text):
        message = MIMEMultipart("alternative")
        message["to"] = recipient
        message["subject"] = f"Re: {subject}" if not subject.startswith("Re: ") else subject

        html_text = reply_text.replace("\n","<br>").replace("\\n","<br>")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset = "utf-8">
            <meta name = "viewport" content = "width-device-width, initial-scale = 1.0">

        </head>
        <body>{html_text}</body>
        </html>
        """

        html_part = MIMEText(html_content,"html")
        message.attach(html_part)

        return message

    def _create_reply_message(self, email, reply_text, send = False):
        message = self._create_html_email_message(
            recipient = email.sender,
            subject = email.subject,
            reply_text = reply_text
        )

        if email.messageId:
            message["In-Reply-To"] = email.messageId

            message["References"] = f"{email.references} {email.messageId}".strip()

            if send:
                message["Message-ID"] = f"<{uuid.uuid4()}@gmail.com"

        body = {
            "raw": base64.urlsafe_b64encode(message.as_bytes()).decode(),
            "threadId":email.threadId
        }

        return body

    def create_draft_reply(self, initia_email, reply_text):
        try:
            message = self._create_reply_message(initia_email,reply_text)

            draft = self.service.users().drafts().create(
                userId = "me", body = {"message": message}
            ).execute()

            return draft
        except Exception as error:
            print(f"An error occured while creating draft : {error}")
            return None
    
    def send_reply(self, initial_email,reply_text):
        try:
            message = self._create_reply_message(initial_email,reply_text,send =True)

            send_message = self.service.users().messages().send(
                userId = "me",body = message
            ).execute()

            return send_message
        except Exception as error:
            print(f"An error occured while sending the email {error}")
            return None

            






