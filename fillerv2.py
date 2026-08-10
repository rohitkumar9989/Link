from langchain_core.tools import tool
from browser_use import BrowserSession, Agent, ChatGoogle, ChatGroq, ChatOllama
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from stagehand import Stagehand
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import List, Optional
import requests
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By

driver_path = r"chromedriver.exe"

service = Service(driver_path)
    
options=Options()
options.add_argument("--remote-debugging-port=5677")
driver = webdriver.Chrome(service=service, options=options)

    # Selenium opens the website
driver.get(
        "https://adscholars.keka.com/careers/applyjob/134011?source=linkedin"
    )
cdp_url="http://127.0.0.1:5677"




class Filler_state(TypedDict):
    cdp_url: str
    MCP_MSG: []
    api_keys_groq: list
    index: 0
    what_to_do: str

with open("resume.json", "r") as f:
    texts=f.read()

f.close()


def backtracer(d):
    if isinstance(d, str):
        return f"value '{d}'"
    if isinstance(d, list):
        if not d:  
            return "no items"
        list_items = [backtracer(item) for item in d]
        return f"a list containing: [{', '.join(list_items)}]"
    if isinstance(d, dict):
        text_segments = []
        for key, value in d.items():
            if value:
                text_segments.append(f"Question {key} has answer {backtracer(value)}")
            else:
                text_segments.append(f"{key} has no items")
        
        return ", ".join(text_segments)
        
    return str(d)

information=backtracer(json.loads(texts))

#checker

class Structure_for_generation_content(BaseModel):
    to_be_filled: List[str] = Field(
        description="A list where each item is a single string containing BOTH the question and its answer in the format: 'Question: [text] | Answer: [text]'"
    )
def checker_class (state: Filler_state)->Filler_state:
    @dataclass
    class MissingField:
        tag: str
        field_type: str
        name: Optional[str]
        field_id: Optional[str]
        label: Optional[str]
        reason: str  # "empty", "no option selected", "not checked", ...
    
        def __str__(self):
            identifier = self.label or self.name or self.field_id or f"<unnamed {self.tag}>"
            return f"- {identifier}  ({self.reason})"
    
    
    AUTO_REQUIRED_SELECTOR = (
        "input[required], textarea[required], select[required], "
        "[aria-required='true']"
    )
    
    PLACEHOLDER_OPTION_TEXT = {"select", "select...", "choose", "choose...", "-- select --", "please select"}
    
    
    def _find_label_text(driver: WebDriver, el: WebElement) -> Optional[str]:
        """Best-effort lookup of a human-readable label for this field."""
        field_id = el.get_attribute("id")
        if field_id:
            try:
                label = driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                text = label.text.strip()
                if text:
                    return text
            except Exception:
                pass
        try:
            parent_label = el.find_element(By.XPATH, "./ancestor::label[1]")
            text = parent_label.text.strip()
            if text:
                return text
        except Exception:
            pass
        placeholder = el.get_attribute("placeholder")
        return placeholder.strip() if placeholder else None
    
    
    def _select_is_empty(el: WebElement) -> Optional[str]:
        value = el.get_attribute("value")
        if not value or value.strip() == "":
            return "no option selected"
        try:
            selected_option = el.find_element(By.CSS_SELECTOR, "option:checked")
            if selected_option.get_attribute("disabled"):
                return "placeholder option still selected"
            if selected_option.text.strip().lower() in PLACEHOLDER_OPTION_TEXT:
                return "placeholder option still selected"
        except Exception:
            pass
        return None
    
    
    def _field_is_empty(el: WebElement) -> Optional[str]:
        """Returns a reason string if unfilled, else None."""
        tag = el.tag_name.lower()
        field_type = (el.get_attribute("type") or "").lower()
    
        if tag == "select":
            return _select_is_empty(el)
    
        if field_type == "checkbox":
            return None if el.is_selected() else "not checked"
    
        if field_type == "radio":
            return None  # handled at group level in find_missing_fields
    
        value = el.get_attribute("value")
        if value is None or value.strip() == "":
            return "empty"
        return None
    
    
    def find_missing_fields(
        driver: WebDriver,
        scope: Optional[WebElement] = None,
        required_selectors: Optional[list] = None,
    ) -> list:
        """
        Scans the live page (or a scoped element like a specific <form>) and
        returns a list of MissingField for anything still unfilled.
    
        scope:              limit the scan to inside this element (e.g. a <form>).
                             Defaults to the whole page.
        required_selectors: extra CSS selectors to treat as required, for sites
                             that don't mark fields with `required`/`aria-required`.
        """
        root = scope if scope is not None else driver
    
        elements = list(root.find_elements(By.CSS_SELECTOR, AUTO_REQUIRED_SELECTOR))
    
        if required_selectors:
            for sel in required_selectors:
                elements.extend(root.find_elements(By.CSS_SELECTOR, sel))
    
        # de-duplicate while preserving order (same element found via 2 selectors)
        seen_ids = set()
        unique_elements = []
        for el in elements:
            key = el.id  # selenium's internal element reference id
            if key not in seen_ids:
                seen_ids.add(key)
                unique_elements.append(el)
    
        missing = []
        seen_radio_groups = set()
    
        for el in unique_elements:
            try:
                if not el.is_displayed():
                    continue  # skip hidden fields
            except Exception:
                continue  # stale element, skip
    
            tag = el.tag_name.lower()
            field_type = (el.get_attribute("type") or "").lower()
            name = el.get_attribute("name")
            field_id = el.get_attribute("id")
    
            if field_type == "radio":
                group_key = name or field_id
                if group_key in seen_radio_groups:
                    continue
                seen_radio_groups.add(group_key)
                radios = (
                    driver.find_elements(By.CSS_SELECTOR, f"input[type='radio'][name='{name}']")
                    if name else [el]
                )
                if not any(r.is_selected() for r in radios):
                    # missing.append(MissingField(
                    #     tag="input", field_type="radio", name=name, field_id=field_id,
                    #     label=_find_label_text(driver, el), reason="no option selected",
                    # ))
                    missing.append([_find_label_text(driver, el), "no options"])
                continue
    
            reason = _field_is_empty(el)
            if reason:
                # missing.append(MissingField(
                #     tag=tag, field_type=field_type or tag, name=name, field_id=field_id,
                #     label=_find_label_text(driver, el), reason=reason,
                # ))
                missing.append([_find_label_text(driver, el), reason])
    
        return missing
    
    
    def ready_to_submit(driver: WebDriver, scope: Optional[WebElement] = None,
                         required_selectors: Optional[list] = None) -> bool:
        return len(find_missing_fields(driver, scope, required_selectors)) == 0
    
    
    def report(driver: WebDriver, scope: Optional[WebElement] = None,
               required_selectors: Optional[list] = None) -> str:
        missing = find_missing_fields(driver, scope, required_selectors)
        return missing

    if ready_to_submit(driver):
        state["MCP_MSG"]=["Filled"]
    else:
        state["MCP_MSG"]=report(driver)
    print(report(driver))
    return state

    
#second_state

async def input_missing_text_2(cdp_url,mcp_msg, api_keys_groq, index):
    prompt=ChatPromptTemplate.from_messages([(
        "system", """
        You are an intelligent AI system who answers the question as a HR
    
        You would be asked questions and answer them using the candidates resume
    
        Make sure you put in the question and then the answer:
    
        For example
    
        - First Name
        -lastName
    
        Answer: 
        First Name is Rohith
        Last Name is Kumar
    
    
        here is the resume of the user: 
    
        {backstory}
        
        """
    ), ("human", "Questions: \n{questions}"), ("assistant", "Answer: \n")])
    
    
    model=small_model.with_structured_output(Structure_for_generation_content)
    
    chain=prompt | model
    
    result=chain.invoke({
        "backstory":information,
        "questions": " ".join(map(str, (m[0] for m in mcp_msg)))
    })
    client=Stagehand(
        server="local",
        model_api_key=api_keys_groq[index]
    )
    cdp_info=requests.get(cdp_url+"/json/version").json()
    ws_url=cdp_info["webSocketDebuggerUrl"]

    session=client.sessions.start(
        model_name= "groq-llama-3.3-70b-versatile",
        browser={
            "type":"local",
            "cdpUrl": ws_url
        }
    )

    session_id=session.data.session_id
    idx=0

    print (mcp_msg, result.to_be_filled)
    for idx,answer in enumerate(mcp_msg):
        if answer[-1]=="empty":
            soln=client.sessions.act(
                id=session_id,
                input=f"Fill the input field {result.to_be_filled[idx]}"
            )
            print(soln.data)
        else:
            soln=client.sessions.act(
                id=session_id,
                input=f"select the choose field {result.to_be_filled[idx]}"
            )
            print(soln.data)
    
    return "Done"

async def input_missing_text_2_init(state: Filler_state)->Filler_state:
    result=await input_missing_text_2(state["cdp_url"],state["MCP_MSG"], state["api_keys_groq"], state["index"])
    

    


    

#Last State:
async def input_missing_text_3(cdp_url, mcp_msg):
    """Use this tool to intelligently fill the code"""

    

    browser_session=BrowserSession(cdp_url=cdp_url)
    try:

        llm = ChatGoogle(
            model="gemini-2.5-flash",
            api_key="KEy",
            temperature=0
        )
    
        questions="Fill the fields with the following inputs: "
    
        for elements in get_interactive_elements(driver):
            if elements["aria_label"] or elements["name"] or elements["placeholder"] and elements["type"]=="text":
                questions+=f"Here is the {elements["aria_label"] or elements["name"] or elements["placeholder"]}\n"
        
        
    
        #Finding all the input elements
        from langchain_classic.prompts import ChatPromptTemplate, MessagesPlaceholder
        prompt=ChatPromptTemplate.from_messages([(
            "system", """You are an intelligent question-answering bot for job applications.
    
    You are given information about a candidate.
    
    Use that information to answer the requested job-application fields.
    
    Return concise answers suitable for directly entering into form fields.
    Do not invent information that is not present in the candidate information.

    Each question in new line is independent of each other, so treat them as different
    
    Candidate information:
    {backstory}
            """
        ), ("human", "{question}"),("assistant", "Here is the answer for question asked: ")])
    
        final_text="Answer the following fields from the metadata provided"
    
        for elements in get_interactive_elements(driver):
            if elements["aria_label"] or elements["name"] or elements["placeholder"] and elements["type"]=="text":
                final_text+=f"Here is an input field.{elements["aria_label"] or elements["name"] or elements["placeholder"]}\n"
    
        chain=prompt | small_model| StrOutputParser()
    
        output=chain.invoke({
            "backstory": information,
            "question": " ".join(map(str, mcp_msg))
        })
    
        agent = Agent(
                task=f"""
                You are already inside an existing browser session.
        
                {output}
        
                Do not navigate anywhere.
                Do not close the browser.
                """,
        
                llm=llm,
        
                browser_session=browser_session,
            use_vision=True
            )
        
        
        result = await agent.run()
        print(result)
    except Exception as e:
        print("Error e has occured: ", e)
        

    
    
    
async def input_missing_text_3_init(state: Filler_state)->Filler_state:
    result=await input_missing_text_3(state["cdp_url"], state["MCP_MSG"])


graph=StateGraph(Filler_state)

graph.add_node("input_missing_text_2_init", input_missing_text_2_init)
graph.add_node("input_missing_text_3_init", input_missing_text_3_init)
graph.add_node("checker1", checker_class)
graph.add_node("checker2", checker_class)
graph.add_node("checker3", checker_class)


#node connections

graph.add_edge(START, "checker1")

graph.add_conditional_edges(
    "checker1",
    lambda state: "end" if len(state["MCP_MSG"][0])<=1 else "continue",{
        "end": END,
        "continue": "input_missing_text_2_init"
    }
)

graph.add_edge("input_missing_text_2_init", "checker2")
graph.add_conditional_edges(
    "checker2",
    lambda state: "end" if len(state["MCP_MSG"][0])<=1 else "continue",{
        "end": END,
        "continue": "input_missing_text_3_init"
    }
)
graph.add_edge("input_missing_text_3_init", "checker3")
graph.add_conditional_edges(
    "checker3",
    lambda state: "end" if len(state["MCP_MSG"][0])<=1 else "continue",{
        "end": END,
        "continue": END
    }
)

app=graph.compile()
# app.invoke({
#     "cdp_url":cdp_url,
#     "api_keys_groq":[""],
#     "index":0,
#     "what_to_do":"Fill the name with K Rohith Kumar and select the nationality with Indian"
# })

time.sleep(9)

result = await app.ainvoke({
    "cdp_url": cdp_url,
    "api_keys_groq": ["keys"],
    "index": 0,
})
    
