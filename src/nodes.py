from colorama import Fore, Style
from .agents import Agents
from .tools.GmailTools import GmailToolsClass
from .state import GraphState, Email

class Nodes:

    def __init__(self):
        self.agents = Agents()
        self.gmail_tools = GmailToolsClass()

    def load_new_emails(self, state: GraphState) -> GraphState:

        print(Fore.YELLOW  + "Load New email")

        recent_emails = self.gmail_tools.fetch_unanswered_emails()
        emails = [Email(**email) for email in recent_emails]

        return {"emails":emails}
    
    def check_new_emails(self, state: GraphState) -> str:
        if(len(state["emails"])==0):
            print(Fore.RED + "No new emails" + Style.RESET_ALL)
            return "empty"
        else:
            print(Fore.GREEN + "New emails to process" + Style.RESET_ALL)
            return "process"
        
    def is_email_inbox_empty(self, state: GraphState) -> GraphState:
        return state

    def categorize_email(self,state: GraphState) -> GraphState:
        print(Fore.YELLOW + "Checking email category...\n" + Style.RESET_ALL)
        current_email = state["emails"][-1]
        result = self.agents.categorize_email.invoke({"email": current_email.body})
        print(Fore.MAGENTA + f"Email category: {result.category.value}" + Style.RESET_ALL)
        return {
            "email_category": result.category.value,
            "current_email":current_email
        }
    
    def route_email_based_on_category(self, state: GraphState) -> str:
        print(Fore.YELLOW + "Routing email based on category...\n" + Style.RESET_ALL)
        category = state["email_category"]

        if category == "product_enquiry":
            return "product related"
        elif category == "unrelated":
            return "unrelated"
        else:
            return "not product related"
        
    def construct_rag_queries(self, state: GraphState)-> GraphState:
        print(Fore.YELLOW + "Designing RAG query...\n" + Style.RESET_ALL)
        email_content = state["current_email"].body
        query_result = self.agents.design_rag_queries.invoke({"email":email_content})

        return {"rag_queries": query_result.queries}
    
    def retrieve_from_rag(self, state: GraphState)-> GraphState:
        print(Fore.YELLOW + "Retrieving information from internal knowledge...\n" + Style.RESET_ALL)
        final_answer = ""

        for query in state["rag_queries"]:
            rag_result  = self.agents.generate_rag_answer.invoke(query)
            final_answer += query + "\n" + rag_result + "\n\n"

        return {"retrieved_documents": final_answer}
    
    def write_draft_email(self, state: GraphState) -> GraphState:
        print(Fore.YELLOW + "Writing draft email...\n" + Style.RESET_ALL)
        inputs = (
            f"# **Email category:** {state["email_category"]}\n\n"
            f"# **Email Content:**\n{state["current_email"].body}\n\n"
            f"# **Information:**\n{state["retrieved_documents"]}"
        )

        writer_messages = state.get("write_messages",[])

        draft_result = self.agents.email_writer.invoke(
            {
                "email_information":inputs,
                "history":writer_messages
            }
        )
        email = draft_result.email
        trials = state.get("trials",0) + 1
        writer_messages.append(f"**Draft{trials}:**\n{email}")
        return {
            "generated_email":email,
            "trials":trials,
            "write_messages":writer_messages
        }
    
    def verify_generated_email(self, state: GraphState)-> GraphState:
        print(Fore.YELLOW + "Verifying generated email...\n" + Style.RESET_ALL)
        review = self.agents.email_proofreader.invoke(
            {
                "initial_email":state["current_email"].body,
                "generated_email":state["generated_email"]
            }
        )

        writer_messages = state.get("write_messages",[])
        writer_messages.append(f"**Proofreader Feedback:**\n {review.feedback}")
        return {
            "sendable":review.send,
            "write_messages":writer_messages
        }
    
    def must_rewrite(self, state: GraphState)-> str:
        email_sendable = state["sendable"]
        if email_sendable:
            state["emails"].pop()
            state["write_messages"] = []
            return "send"
        
        elif state["trials"]>=3:
            state["emails"].pop()
            state["write_messages"] = []
            return "stop"
        else:
            return "rewrite"
        
    def create_draft_response(self, state: GraphState)-> GraphState:
        print(Fore.YELLOW + "Creating draft email...\n" + Style.RESET_ALL)
        self.gmail_tools.create_draft_reply(state["current_email"], state["generated_email"])

        return {"retrieved_documents":"", "trials":0}
    
    def send_email_response(self, state: GraphState) -> GraphState:
        print(Fore.YELLOW + "Sending email...\n" + Style.RESET_ALL)
        self.gmail_tools.send_reply(state["current_email"],state["generated_email"])
        return {"retrieved_documents":"", "trials":0}
    
    def skip_unrelated_email(self, state):
        state["emails"].pop()
        return state
