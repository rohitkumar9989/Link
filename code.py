model = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.9,
        api_key=""
    )
small_llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.6,
        api_key=""
    )

@tool
def understand_project()->str:
    """Use this function to understand whether the original resume projects properly align with the Job Description"""
    prroject_text="""Effective Data Visualization Tool:
Built an AI-powered EDA and visualization platform using Python, Streamlit, LangChain, and HuggingFace models. The system dynamically generated charts, handled missing data automatically, and enabled NLP-based dataset querying through custom AI agents. Demonstrates experience in LLM integration, AI workflow orchestration, intelligent automation, NLP systems, and interactive ML application development.

AI-Powered Legacy System Migration Assistant:
Developed an AI-driven migration assistant using LangChain, Streamlit, FAISS vector DB, and RAG pipelines to support legacy system modernization and framework/database migration tasks. Implemented semantic retrieval, prompt-engineered workflows, and contextual migration assistance, showcasing expertise in Generative AI, vector search systems, backend AI architecture, and intelligent developer tooling."""
    return prroject_text


@tool
def change_project(project_changes:str, reason:str)->None:
    """Use this tool to update the project section ONLY if the current Projects domains are completely irrelevant to the Job Description domains. STRICTLY DO NOT CALL if existing Projects (e.g., in AI, Langchain, Machine Learning, FAISS, Deep Learning) are already a good fit. Generate atleast 2 projects which align with the JD"""
    latex_code =r"""\resumeSubHeadingListStart
    \resumeProjectHeading
        {\textbf{PROJECT NAME} $|$ }{}
        \resumeItemListStart
            \resumeItem{text explaining the project}
        \resumeItemListEnd 
    \resumeSubHeadingListEnd"""
    prompt=ChatPromptTemplate.from_messages([("assistant", "You are a intelligent resume maker, you would be provided with the content, of what should be placed in the latex template, you have to intelligently only provide the updated latex template"),
                                            ("user", """Here is the changes that have to be made:  {project_changes} along with the explanation of project in the resume item below in the latex code  due to reason {reason}, Here is the latex code  {latex_code}
                                            Strictly generate the output like the latex code, no extra explanation needed as we would be pasting whatever you give directly in the resume latex."""),
                                            ("ai", """%-----------PROJECTS-----------
\section""")])
        
    chain=prompt | small_llm | StrOutputParser()
    output=chain.invoke({
        "project_changes":project_changes,
        "latex_code":latex_code,
        "reason":reason
    })
    with open ("updates.txt","w") as f:
        f.write(output)
    return None



#@tool
#def understand_certificates()->str:

    return 
tools=[understand_project, change_project]
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are an intelligent ATS and resume updation machine.
Based upon the requirements given, implement the changes in the original resume. **IF NEEDED** change the project according to the Job description welll fitted project.
 First call understand project to understand the the project and help you tally 
"""
    ),
    ("human", "{JD}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])
agent = create_tool_calling_agent(
    llm=model,
    tools=tools,
    prompt=prompt
)
final_agent = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True
)
final_agent.invoke({

        "JD": """
    
Architect and lead the delivery of scalable, cloud-native software systems across backend and frontend layers. ﻿﻿Own end-to-end design and implementation of GenAl and LLM-powered platform capabilities in production. ﻿﻿Design and govern multi-agent Al architectures using MCP, A2A, and emerging agentic frameworks. ﻿﻿Define containerisation, orchestration, and deployment standards using Docker, Kubernetes, and Helm. ﻿﻿Lead architectural reviews, establish engineering best practices, and set technical direction for the team. ﻿﻿Drive cross-functional technical collaboration with product, data science, security, and infrastructure teams. Identify and resolve systemic technical risks across services, APIs, and data pipelines. ﻿﻿Mentor junior engineers through pairing, code reviews, and structured knowledge transfer. ﻿﻿Champion observability, reliability, and security practices across the platform. Familiarity with Agentic AI/Multi Agent orchestration frameworks like OpenAI agents SDK, LangGraph, etc is desired Experience with workflow management tools like Temporal, Airflow
    """
    })




        
    
