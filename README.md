# AI Knowledge System

基于 **FastAPI + Streamlit + PostgreSQL + pgvector + RAG** 构建的多用户企业 AI 知识库问答系统。

项目面向企业内部知识查询场景，支持用户注册登录、JWT 身份认证、多用户数据隔离、PDF 知识库管理、Embedding、Hybrid Search、BGE Reranker、Qwen 大模型问答、流式响应、历史会话管理、统一异常处理、日志记录以及自动化测试。

---

## 1. 项目介绍

本项目实现了一个完整的企业 AI 知识库问答应用。

用户登录后，可以上传企业内部 PDF 文档，系统自动完成：

```text
PDF
 ↓
文本提取
 ↓
文本切分
 ↓
Embedding 向量化
 ↓
PostgreSQL + pgvector
 ↓
Hybrid Search
 ↓
BGE Reranker
 ↓
构建知识上下文
 ↓
Qwen 大模型
 ↓
流式回答
```

系统同时具备用户级数据隔离：

```text
用户 A
 ├── 聊天 Session
 ├── 聊天记录
 └── 知识库文档

用户 B
 ├── 聊天 Session
 ├── 聊天记录
 └── 知识库文档
```

用户只能访问、修改和检索属于自己的数据。

---

# 2. 项目核心能力

## 2.1 用户认证

系统采用 JWT 进行用户身份认证。

支持：

* 用户注册
* 用户登录
* 密码哈希
* JWT Token
* Token 过期校验
* 当前用户信息查询
* Streamlit 前端登录
* Streamlit 退出登录
* Token 自动附加到后续请求

认证流程：

```text
用户名 + 密码
      ↓
POST /login
      ↓
验证用户
      ↓
生成 JWT
      ↓
Streamlit 保存 Token
      ↓
后续 API 自动携带 Authorization
```

请求格式：

```http
Authorization: Bearer <JWT>
```

---

## 2.2 多用户数据隔离

项目不仅验证用户是否登录，还进一步实现了用户级资源隔离。

### 聊天数据隔离

```text
chat_sessions.user_id
        ↓
users.id
```

用户只能查看、删除和使用自己的 Session。

### 知识库数据隔离

```text
documents.user_id
        ↓
users.id
```

用户只能查看、上传、删除和检索自己的知识库。

例如：

```text
testuser
user_id = 1
    ↓
只能访问 user_id = 1 的资源

testuser2
user_id = 2
    ↓
只能访问 user_id = 2 的资源
```

即使用户直接猜测其他用户的 `session_id`，后端也会进行权限检查。

---

# 3. RAG 知识库

## 3.1 PDF 上传

用户上传 PDF 后，系统自动完成：

```text
PDF
 ↓
pypdf
 ↓
页面文本提取
 ↓
RecursiveCharacterTextSplitter
 ↓
Chunk
 ↓
Embedding
 ↓
PostgreSQL + pgvector
```

每个文档 Chunk 会记录：

```text
user_id
content
embedding
filename
page_number
chunk_id
created_at
```

---

## 3.2 文本切分

使用 LangChain 的：

```text
RecursiveCharacterTextSplitter
```

当前主要参数：

```text
chunk_size = 300
chunk_overlap = 50
```

通过页面文本切分为多个 Chunk，方便后续向量检索。

---

# 4. Hybrid Search

系统不是只依赖向量检索，而是同时使用：

```text
向量检索
    +
关键词检索
    ↓
加权融合
    ↓
Hybrid Search
```

当前实现：

```text
Vector Weight  = 0.7
Keyword Weight = 0.3
```

向量检索负责语义相关性。

关键词检索用于补充精确词语匹配。

最终将两种检索结果进行融合排序。

并且检索过程中始终带有当前用户的 `user_id` 条件，因此不会检索到其他用户的知识库。

---

# 5. BGE Reranker

Hybrid Search 得到候选文档后，进一步使用 BGE Reranker 进行二次排序：

```text
Hybrid Search
      ↓
候选文档
      ↓
BGE Reranker
      ↓
Top-K
      ↓
构建上下文
      ↓
Qwen
```

这样可以进一步提高进入大模型上下文的文档相关性。

---

# 6. AI 问答

聊天流程：

```text
用户问题
   ↓
JWT 身份验证
   ↓
检查 Session 所属用户
   ↓
Query Embedding
   ↓
当前用户知识库
   ↓
Hybrid Search
   ↓
BGE Reranker
   ↓
RAG Context
   ↓
Qwen
   ↓
StreamingResponse
   ↓
保存聊天记录
```

回答结束后，同时返回参考来源。

例如：

```text
📚 参考来源：
- 企业AI知识库测试文档.pdf 第1页 chunk_3
- 企业AI知识库测试文档.pdf 第1页 chunk_1
```

---

# 7. 聊天系统

支持：

* 创建聊天
* 新建聊天
* 历史聊天列表
* 查看历史消息
* 删除聊天
* 多轮对话
* AI 流式输出
* 自动生成聊天标题
* Session 与用户绑定

数据结构：

```text
users
  │
  └── chat_sessions
          │
          └── chat_messages
```

---

# 8. 前端

前端使用：

```text
Streamlit
```

主要功能：

* 登录
* 注册
* 当前用户信息
* 退出登录
* 新建聊天
* 历史聊天
* 删除聊天
* PDF 上传
* 知识库列表
* 知识库删除
* AI 流式问答

前端登录后的请求会自动附加：

```http
Authorization: Bearer <JWT>
```

因此用户不需要手动操作 JWT。

---

# 9. 后端 API

## 用户认证

### 用户注册

```http
POST /register
```

### 用户登录

```http
POST /login
```

### 当前用户

```http
GET /me
```

---

## 聊天

### 创建 Session

```http
POST /session
```

### 获取当前用户聊天

```http
GET /sessions
```

### 获取聊天消息

```http
GET /sessions/{session_id}/messages
```

### 删除聊天

```http
DELETE /sessions/{session_id}
```

### AI 问答

```http
POST /chat
```

---

## 知识库

### 上传 PDF

```http
POST /upload
```

### 获取当前用户知识库

```http
GET /documents
```

### 删除知识库文件

```http
DELETE /documents/{filename}
```

---

# 10. 数据库设计

使用：

```text
PostgreSQL
+
pgvector
```

主要数据表：

```text
users
chat_sessions
chat_messages
documents
```

关系：

```text
users
 │
 ├── chat_sessions
 │       │
 │       └── chat_messages
 │
 └── documents
```

---

## 10.1 users

保存用户基本信息。

主要字段：

```text
id
username
password_hash
created_at
```

---

## 10.2 chat_sessions

保存聊天会话。

主要字段：

```text
id
title
created_at
user_id
```

---

## 10.3 chat_messages

保存聊天内容。

主要字段：

```text
id
user_message
ai_message
created_at
session_id
```

---

## 10.4 documents

保存知识库 Chunk。

主要字段：

```text
id
content
embedding
filename
page_number
chunk_id
user_id
created_at
```

其中：

```text
embedding
```

使用 pgvector 的 `vector` 类型存储。

---

# 11. 数据库初始化

项目提供：

```text
database/init.sql
```

用于新环境初始化数据库。

包含：

```text
pgvector 扩展
users
chat_sessions
chat_messages
documents
外键约束
索引
```

主要索引包括：

```text
idx_chat_sessions_user_id
idx_chat_messages_session_id
idx_documents_user_id
idx_documents_user_filename
```

---

# 12. 项目结构

```text
ai-knowledge-system/
│
├── app/
│   ├── main.py
│   ├── database.py
│   ├── auth.py
│   ├── logger.py
│   ├── embedding.py
│   ├── rerank.py
│   │
│   └── services/
│       └── qwen_services.py
│
├── frontend/
│   ├── streamlit_app.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── database/
│   └── init.sql
│
├── test/
│   ├── test_auth.py
│   └── test_api.py
│
├── .env
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

---

# 13. 环境要求

推荐运行环境：

```text
Python 3.11
PostgreSQL
pgvector
Git
Docker
Docker Compose
```

---

# 14. 环境变量

项目通过 `.env` 管理敏感配置。

创建：

```text
.env
```

参考 `.env.example`：

```env
# PostgreSQL
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=ai_knowledge
DB_USER=postgres
DB_PASSWORD=your_database_password

# JWT
JWT_SECRET_KEY=your_random_secret_key

# Qwen / DashScope
DASHSCOPE_API_KEY=your_api_key
```

注意：

```text
.env
```

包含真实密码、JWT 密钥和 API Key，不能提交到 GitHub。

项目 `.gitignore` 已包含：

```text
.env
```

---

# 15. Windows 本地运行

## 安装后端依赖

```powershell
pip install -r requirements.txt
```

安装测试依赖：

```powershell
pip install -r requirements-dev.txt
```

---

## 初始化数据库

准备 PostgreSQL 数据库：

```text
ai_knowledge
```

启用 pgvector 后执行：

```text
database/init.sql
```

---

## 启动 FastAPI

```powershell
uvicorn app.main:app --reload
```

Swagger：

```text
http://127.0.0.1:8000/docs
```

---

## 启动 Streamlit

另开一个终端：

```powershell
streamlit run frontend\streamlit_app.py
```

---

# 16. Docker 部署

项目提供：

```text
Dockerfile
frontend/Dockerfile
docker-compose.yml
```

当前 Docker Compose 目标架构：

```text
Docker Compose
      │
      ├── PostgreSQL + pgvector
      │
      ├── FastAPI Backend
      │
      └── Streamlit Frontend
```

服务之间通过 Docker 网络通信：

```text
frontend
   ↓
backend:8000
   ↓
db:5432
```

Backend 使用：

```text
DB_HOST=db
```

Frontend 使用：

```text
BACKEND_URL=http://backend:8000
```

---

## Docker 服务

### PostgreSQL

```text
db
```

负责：

```text
users
chat_sessions
chat_messages
documents
pgvector
```

---

### FastAPI

```text
backend
```

默认端口：

```text
8000
```

---

### Streamlit

```text
frontend
```

默认端口：

```text
8501
```

---

## Docker 启动

配置好 `.env` 后：

```powershell
docker compose up -d --build
```

查看：

```powershell
docker compose ps
```

查看日志：

```powershell
docker compose logs -f
```

停止：

```powershell
docker compose down
```

---

# 17. 日志与异常处理

项目提供统一日志系统：

```text
app/logger.py
```

日志示例：

```text
2026-xx-xx xx:xx:xx | INFO | ai-knowledge-system | POST /login -> 200
2026-xx-xx xx:xx:xx | INFO | ai-knowledge-system | 创建聊天成功
2026-xx-xx xx:xx:xx | WARNING | ai-knowledge-system | GET /... -> 403
```

系统统一处理：

```text
401
403
422
500
```

例如权限错误：

```json
{
  "code": 403,
  "message": "无权访问该聊天会话"
}
```

参数错误：

```json
{
  "code": 422,
  "message": "请求参数错误"
}
```

服务器内部错误：

```json
{
  "code": 500,
  "message": "服务器内部错误"
}
```

---

# 18. 自动化测试

测试代码位于：

```text
test/
```

运行：

```powershell
python -m pytest -q
```

当前测试覆盖：

```text
密码哈希
JWT 创建与解析
用户注册
用户登录
401 未认证
422 参数错误
聊天用户隔离
聊天越权
知识库用户隔离
知识库越权
```

当前版本测试结果：

```text
11 passed
```

说明当前核心认证和权限逻辑已经通过自动化测试。

---

# 19. 安全设计

当前项目已经实现：

```text
密码哈希
JWT 身份认证
Token 过期校验
Session 用户隔离
聊天消息用户隔离
知识库用户隔离
RAG 用户级检索
越权访问拦截
统一异常处理
敏感配置与 Git 分离
```

后端会在访问用户资源之前检查：

```text
当前 JWT user_id
        ↓
资源所属 user_id
        ↓
是否一致
```

不一致时直接拒绝访问。

---

# 20. 当前项目状态

当前已经完成：

```text
项目基础架构              ✅
FastAPI                   ✅
Streamlit                 ✅
PostgreSQL                ✅
pgvector                  ✅

PDF 上传                  ✅
PDF 文本提取              ✅
文本切分                  ✅
Embedding                 ✅
Hybrid Search             ✅
BGE Reranker              ✅
RAG                       ✅
Qwen                      ✅
流式回答                  ✅

用户注册                  ✅
用户登录                  ✅
密码哈希                  ✅
JWT                       ✅
用户信息                  ✅
退出登录                  ✅

聊天 Session              ✅
历史聊天                  ✅
聊天记录                  ✅
聊天删除                  ✅
聊天用户隔离              ✅

知识库管理                ✅
知识库用户隔离            ✅
RAG 用户级检索            ✅

统一异常处理              ✅
日志                      ✅
pytest 自动化测试         ✅

Docker 配置               ✅
数据库初始化脚本          ✅
Git / GitHub              ✅
```

---

# 21. 当前测试结果

核心功能已经进行了实际验证，包括：

```text
testuser
    ↓
登录
    ↓
创建聊天
    ↓
读取自己的聊天
    ↓
上传知识库
    ↓
RAG 问答
```

同时验证：

```text
testuser2
    ↓
无法读取 testuser 的聊天
    ↓
无法读取 testuser 的知识库
    ↓
无法使用 testuser 的 Session
    ↓
越权请求返回 403
```

自动化测试：

```text
11 passed
```

---

# 22. 后续扩展

当前版本暂未加入 Agent / Tool Calling。

后续可以扩展：

```text
AI Agent
Tool Calling
订单查询
用户信息查询
业务数据库
Workflow
多工具协同
```

进一步形成：

```text
                  ┌── 企业知识库 RAG
                  │
用户 → AI Agent ──┼── 用户信息 Tool
                  │
                  ├── 订单查询 Tool
                  │
                  └── 业务系统 Tool
```

---

# 23. 项目目标

本项目的目标是构建一个具备完整应用链路的企业 AI 知识库系统：

```text
用户
 ↓
前端
 ↓
JWT 身份认证
 ↓
FastAPI
 ↓
PostgreSQL
 ↓
企业知识库
 ↓
Embedding
 ↓
Hybrid Search
 ↓
Reranker
 ↓
RAG
 ↓
Qwen
 ↓
流式回答
```

同时具备：

```text
多用户
+
权限控制
+
数据隔离
+
自动化测试
+
日志
+
Docker
+
版本管理
```

当前版本以 **RAG 企业知识库问答**为核心，后续可以进一步向企业 AI Agent 和业务自动化方向扩展。
