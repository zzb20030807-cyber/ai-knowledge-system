from sentence_transformers import CrossEncoder


# 加载 rerank 模型
model = CrossEncoder(
    "BAAI/bge-reranker-base"
)


def rerank_documents(
        query,
        documents,
        top_k=3
):
    """
    对检索出来的文档进行重新排序

    query:
        用户问题

    documents:
        Hybrid Search返回的候选文本

    top_k:
        最终保留数量
    """


    # 构造模型输入
    pairs = []

    for doc in documents:

        pairs.append(
            [
                query,
                doc
            ]
        )


    # 模型计算相关性分数
    scores = model.predict(pairs)


    # 文档和分数绑定
    results = list(
        zip(
            documents,
            scores
        )
    )


    # 按分数从高到低排序
    results.sort(
        key=lambda x:x[1],
        reverse=True
    )


    # 返回top_k文档
    return [
        item[0]
        for item in results[:top_k]
    ]