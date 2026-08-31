"""LangChain v3 事件流实战:astream_events(version="v3") + create_agent()

运行前准备(任选一种方式提供模型配置):
    export OPENAI_API_KEY=sk-xxx
    export OPENAI_BASE_URL=https://api.openai.com/v1   # 可选,兼容 OpenAI 协议的端点
    export OPENAI_MODEL=gpt-4o-mini                    # 可选

运行:
    python examples/stream_agent_demo.py

控制台输出形如:
    [思考中] 用户想比较两个城市的天气...          (模型开启 reasoning 时才有)
    [调用工具] get_weather {"city": "北京"}
    [工具结果] get_weather -> 北京:多云转晴,26°C...
    [答案] 好的,北京的天气是...
"""

import asyncio
import ast
import operator
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv()
# ---------------------------------------------------------------- 工具定义

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("仅支持四则运算")


@tool
def calculator(expression: str) -> str:
    """计算一个四则运算表达式,例如 '2 * (3 + 4)'。"""
    try:
        return str(_safe_eval(ast.parse(expression, mode="eval").body))
    except Exception as e:
        return f"计算失败: {e}"


@tool
def get_weather(city: str) -> str:
    """查询指定城市的当前天气(演示用假数据)。"""
    fake = {
        "北京": "北京:多云转晴,26°C,东南风3级,空气质量良",
        "上海": "上海:小雨,22°C,东风4级,湿度85%",
    }
    return fake.get(city, f"{city}:晴,28°C,微风")


# ---------------------------------------------------------------- Agent

llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    base_url=os.getenv("OPENAI_BASE_URL") or None,
    api_key=os.getenv("OPENAI_API_KEY", "sk-xxx"),
    temperature=0,
)

agent = create_agent(
    model='openai:deepseek-v4-flash',
    system_prompt="你是一个乐于助人的中文助手,回答前先简要规划,再调用工具,最后给出结论。",
    tools=[get_weather, calculator],
)


# ---------------------------------------------------------------- 消费者 1:消息流(思考 / 调用工具参数 / 答案)
async def consume_messages(run) -> None:
    """迭代 run.messages:每次 LLM 调用产生一个 message 流对象。

    message.reasoning   -> 思考内容增量(需模型输出 reasoning block)
    message.tool_calls  -> 模型正在生成的工具调用参数块(部分 JSON)
    message.text        -> 答案文本增量
    message.output      -> await 得到拼装完成的 AIMessage(含 usage_metadata)
    """
    async for message in run.messages:
        # ① 思考中……
        printed_thinking = False
        async for delta in message.reasoning:
            if not printed_thinking:
                print("\n[思考中] ", end="", flush=True)
                printed_thinking = True
            print(delta, end="", flush=True)

        # ② 调用工具(模型生成工具调用参数的过程)
        # async for chunk in message.tool_calls:
        #
        #     name = chunk.get("name") or ""
        #     args = chunk.get("args") or ""
        #     if name:
        #         print(f"\n[调用工具] {name} {args}", end="", flush=True)
        finalized = message.tool_calls.get()
        if finalized:
            print(f"finalized tool calls: {finalized}")

        # ③ 答案逐 token 输出
        printed_answer = False
        async for delta in message.text:
            if not printed_answer:
                print("\n[答案] ", end="", flush=True)
                printed_answer = True
            print(delta, end="", flush=True)
        print()

        # ④ 本次模型调用结束,拿到完整消息(含 token 用量)
        final = await message.output
        usage = getattr(final, "usage_metadata", None)
        if usage:
            print(
                f"    (本次模型调用 tokens: input={usage['input_tokens']}, "
                f"output={usage['output_tokens']})"
            )


# ---------------------------------------------------------------- 消费者 2:工具执行生命周期(工具结果)
async def consume_tool_calls(run) -> None:
    """迭代 run.tool_calls:每次真正的工具执行产生一个 call 流对象。

    call.tool_name / call.input  -> 开始执行时就可用
    call.output_deltas           -> 工具输出增量(普通工具通常一次到位)
    call.output / call.error     -> 终态结果
    """
    async for call in run.tool_calls:
        # 等这个工具调用走完(output_deltas 通道在 tool-finished/tool-error 时关闭)
        async for _delta in call.output_deltas:
            pass  # 流式工具可在这里逐块打印;普通工具没有增量
        if call.error:
            print(f"[工具结果] {call.tool_name} 执行出错: {call.error}")
        else:
            print(f"[工具结果] {call.tool_name} -> {call.output}")


# ---------------------------------------------------------------- 主流程
async def main() -> None:
    user_input = "查一下北京和上海的天气,然后算出两地温差的绝对值,最后给出出行建议。"
    print(f"用户: {user_input}\n")
    input = {'messages': [{'role': 'user', 'content': '查一下北京和上海的天气,然后算出两地温差的绝对值,最后给出出行建议。'}]}
    # 注意:astream_events(version="v3") 返回的是一个协程,必须先 await
    # 才能拿到 AsyncGraphRunStream 对象;多个投影可并发消费(asyncio.gather),
    # 任一投影的迭代都会驱动整条流向前走。
    run = await agent.astream_events(input, version="v3")
    try:
        await asyncio.gather(
            consume_messages(run),
            consume_tool_calls(run),
        )
        final_state = await run.output
        print(f"\n共 {len(final_state['messages'])} 条消息(含中间步骤)")
    except BaseException:
        await run.abort()  # 提前退出时确保后台资源被清理
        raise


if __name__ == "__main__":
    asyncio.run(main())
