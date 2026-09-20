import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DASHSCOPE_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url="https://llm-31i9j7i2voxlzjgz.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
)


# 🟡 修改：使用流式方式获取 AI 回答
def ask_qwen(question: str, context: str = ""):

    try:

        response = client.chat.completions.create(
            model="qwen3.7-plus",
        messages=[
    {
        "role": "system",
        "content": f"""
你是一个企业内部知识库智能问答助手。

请严格根据下面提供的知识库内容回答用户问题。

知识库内容：
{context}

回答要求：
1. 优先使用知识库中的内容回答。
2. 如果知识库中没有相关信息，请明确告诉用户“知识库中没有找到相关信息”。
3. 不要凭空编造知识库中不存在的信息。
"""
    },
    {
        "role": "user",
        "content": question
    }
],

            # 🟢 开启流式输出
            stream=True
        )


        # 🟢 一段一段获取 AI 回复
        for chunk in response:

            # 🟢 先判断 choices 有没有内容
            if not chunk.choices:
                continue

            # 🟢 获取这一段文字
            content = chunk.choices[0].delta.content

            # 🟢 有文字才返回
            if content:
                yield content


    except Exception as e:

        # 🟢 如果发生错误，把错误信息返回
        yield f"发生错误：{str(e)}"