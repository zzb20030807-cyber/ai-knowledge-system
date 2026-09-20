import os
from openai import OpenAI
from dotenv import load_dotenv
from app.database import save_document
from app.database import search_documents
load_dotenv()

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-v4",
        input=text
    )

    return response.data[0].embedding

def get_embeddings(chunks):
    """
    把多个 Chunk 全部转换成向量
    """

    vectors = []

    for chunk in chunks:
        vector = get_embedding(chunk)
        vectors.append(vector)  

    return vectors

if __name__ == "__main__":

    question = "Python 后端 AI 应用开发"

    # 把问题转换成向量
    query_vector = get_embeddings([question])[0]

    # 去数据库寻找最相关的文本
    results = search_documents(query_vector)

    print("问题：", question)

    print("\n最相关的内容：")
 
    for result in results:
        print("--------------------")
        print(result[0])