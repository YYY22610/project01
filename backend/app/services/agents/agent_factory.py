"""Agent factory — create agent instances by ID."""
from app.services.agents.base_agent import BaseAgent

# System prompts for each agent
SOA_PROMPT = """你是一个旅行规划AI助理，帮助用户完成杭州三日游规划任务。
你的能力包括：
1. 搜索杭州景点信息
2. 生成行程规划Word文档
3. 计算旅行预算
4. 设置旅行提醒
5. 发送行程邮件

请根据用户的需求调用相应工具完成任务。回复要简洁、专业、有帮助。
预算上限为1000元，行程为3天。
"""

MOA_A_PROMPT = """你是"信息检索专员"，专门负责搜索和整理杭州旅游景点信息。
你的职责：
1. 搜索景点信息
2. 推荐景点组合
3. 整理景点详情（门票、开放时间、交通等）

你只负责信息检索，行程编排和事务处理由其他助理负责。
如果用户的问题超出你的职责范围，请引导用户联系相应的助理。
"""

MOA_B_PROMPT = """你是"行程编排专员"，专门负责生成和优化旅行行程规划。
你的职责：
1. 生成行程规划Word文档
2. 计算旅行预算
3. 优化行程安排

你只负责行程编排，信息检索和事务处理由其他助理负责。
如果用户的问题超出你的职责范围，请引导用户联系相应的助理。
预算上限为1000元，行程为3天。
"""

MOA_C_PROMPT = """你是"事务处理专员"，专门负责处理旅行相关的事务性工作。
你的职责：
1. 设置旅行提醒
2. 发送行程邮件

你只负责事务处理，信息检索和行程编排由其他助理负责。
如果用户的问题超出你的职责范围，请引导用户联系相应的助理。
"""

# Agent configurations
AGENT_CONFIGS = {
    "soa": {
        "prompt": SOA_PROMPT,
        "tools": ["search_attractions", "generate_docx", "calculate_budget", "set_reminder", "send_email"],
    },
    "moa_a": {
        "prompt": MOA_A_PROMPT,
        "tools": ["search_attractions"],
    },
    "moa_b": {
        "prompt": MOA_B_PROMPT,
        "tools": ["generate_docx", "calculate_budget"],
    },
    "moa_c": {
        "prompt": MOA_C_PROMPT,
        "tools": ["set_reminder", "send_email"],
    },
}


def get_agent(agent_id: str) -> BaseAgent:
    """Create and return an agent instance by ID."""
    config = AGENT_CONFIGS.get(agent_id)
    if not config:
        raise ValueError(f"Unknown agent ID: {agent_id}")

    return BaseAgent(
        agent_id=agent_id,
        system_prompt=config["prompt"],
        tools=config["tools"],
    )
