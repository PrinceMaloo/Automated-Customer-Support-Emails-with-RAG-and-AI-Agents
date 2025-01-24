from pydantic import BaseModel, Field 
from typing import List
from enum import Enum


class EmailCategory(str, Enum):
    product_enquiry = "product_enquiry"
    customer_complain = "customer_complain"
    customer_feedback = "customer_feedback"
    unrelated = "unrelated"


class CategorizeEmailOutput(BaseModel):

    category : EmailCategory = Field(
        ...,
        description = "The category is assigned to the email, indicating its type based on predefined rules"
    )

class RAGQueriesOutput(BaseModel):
    queries : List[str] = Field(
        ...,
        description = "A list of up to three questions representing the customer's intent, based on their email."
    )

class WriteOutput(BaseModel):
    email : str = Field(
        ...,
        description = "The draft email written in response to the customer's inquiry, adhering to company tone and standards."
    )

class ProofReaderOutput(BaseModel):
    feedback : str = Field(
        ...,
        description = "Detailed feedback explaining why the email is or not sendable"
    )

    send: bool = Field(

        ...,
        description = "Indicates whether the email is ready to be sent (true) or requires rewriting (false)."
    )