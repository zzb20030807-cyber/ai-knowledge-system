# AI Knowledge System
基于 FastAPI + Streamlit + PostgreSQL + pgvector + RAG 架构实现的企业级智能知识库问答系统。
## 项目简介
系统支持企业文档上传、文本切分、向量化、混合检索、Rerank 重排序以及大模型问答。 用户上传 PDF 文档后，系统自动完成： PDF 文档 → 文本解析 → 文本切分 → Embedding 向量化 → PostgreSQL + pgvector 存储 → Hybrid Search 检索 → BGE Reranker 
重排序 → Qwen 大模型生成答案
## 技术栈
- Python 3.11 - FastAPI - Streamlit - PostgreSQL - pgvector - OpenAI Compatible API - Qwen - BGE Reranker - Docker - Docker Compose
## 核心功能
### 1. 文档知识库
支持 PDF 文档上传，并自动进行文本切分和向量化。
### 2. 向量检索
使用 PostgreSQL + pgvector 保存文档向量，实现语义检索。
### 3. RAG 问答
根据用户问题检索相关知识，再结合大模型生成回答。
### 4. Rerank
使用 BGE Reranker 对检索结果进行二次排序，提高上下文相关性。
### 5. 对话系统
支持聊天会话以及聊天记录保存。
### 6. Docker 部署
使用 Docker Compose 管理前后端服务，实现一键启动和自动重启。
## 项目结构
```text ai-knowledge-system/ ├── app/ │ ├── main.py │ ├── database.py │ ├── embedding.py │ ├── rerank.py │ └── services/ │ └── qwen_services.py ├── frontend/ │ ├── streamlit_app.py │ ├── Dockerfile │ └── requirements.txt ├── Dockerfile 
├── docker-compose.yml ├── requirements.txt
└── .gitignore
