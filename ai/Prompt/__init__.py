from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from .Prompts import SYSTEM_INSTRUCTIONS_MD, ANSWER_HUMAN_TEMPLATE_MD, PLANNER_ROUTER_PROMPT, GURADRAIL_PROMPT, SMALL_TALK_INSTRUCTION_MD

#Chưa fix
ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(SYSTEM_INSTRUCTIONS_MD),
        HumanMessagePromptTemplate.from_template(ANSWER_HUMAN_TEMPLATE_MD),
    ]
)

SMALL_TALK_ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(SMALL_TALK_INSTRUCTION_MD),
        HumanMessagePromptTemplate.from_template("Hãy trả lời câu hỏi sau một cách thân thiện và tự nhiên:\n\n{question}"),
    ]    
)

GURADRAIL_ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(GURADRAIL_PROMPT),
        HumanMessagePromptTemplate.from_template('User Input: "{user_query}"\nOutput:')
    ]
)