from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from .Prompts import (
    SYSTEM_INSTRUCTIONS_MD,
    ANSWER_HUMAN_TEMPLATE_MD,
    PLANNER_ROUTER_PROMPT,
    GUARDRAIL_PROMPT,
    SMALL_TALK_INSTRUCTION_MD,
    ADVISOR_INSTRUCTION_MD,
    ADVISOR_HUMAN_TEMPLATE_MD,
    ADVISOR_RENDER_SYSTEM_MD,
    ADVISOR_RENDER_HUMAN_MD,
)

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

PLANNER_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(PLANNER_ROUTER_PROMPT),
        HumanMessagePromptTemplate.from_template("Lịch sử gần đây:\n{history}\nUser Input: \"{user_query}\"\nOutput:"),
    ]
)

GUARDRAIL_ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(GUARDRAIL_PROMPT),
        HumanMessagePromptTemplate.from_template(
            'Lịch sử gần đây:\n{history}\nUser Input: "{user_query}"\nOutput:'
        ),
    ]
)

ADVISOR_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(ADVISOR_INSTRUCTION_MD),
        HumanMessagePromptTemplate.from_template(ADVISOR_HUMAN_TEMPLATE_MD),
    ]
)

ADVISOR_RENDER_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(ADVISOR_RENDER_SYSTEM_MD),
        HumanMessagePromptTemplate.from_template(ADVISOR_RENDER_HUMAN_MD),
    ]
)