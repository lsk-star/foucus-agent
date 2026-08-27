from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import ToolMessage

load_dotenv()


def get_weather(location: str):
    """获取天气"""
    return f"{location}天气是晴朗的，温度是25摄氏度"


agent = create_agent(
    model='openai:deepseek-v4-flash',
    system_prompt="你是一个有用的助手，你可以帮助用户完成任务。",
    tools=[get_weather],
)

input = {'messages': [{'role': 'user', 'content': '你是谁,北京天气怎么样'}]}
stream = agent.stream_events(input, version="v3")


def test():
    seen_tool_ids = set()
    for name, item in stream.interleave("messages", "values"):
        if name == "messages":
            msg_stream = item
            for delta in msg_stream.reasoning:
                print(f"[thinking] {delta}", end="", flush=True)
            for delta in msg_stream.text:
                print(delta, end="", flush=True)
            finalized = msg_stream.tool_calls.get()
            if finalized:
                # for tc in finalized:
                print(f"\n[tool call] {finalized})")
            print()
        elif name == "values":
            state = item
            for msg in state.get('messages', []):
                if isinstance(msg, ToolMessage) and msg.id not in seen_tool_ids:
                    seen_tool_ids.add(msg.id)
                    print(f"[tool result] {msg.content}")


if __name__ == '__main__':
    test()