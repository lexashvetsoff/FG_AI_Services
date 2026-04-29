import ollama


# client = ollama.AsyncClient(host='http://10.10.22.203:11434')
# client = ollama.Client(host='http://10.10.22.203:11434')
client = ollama.Client(host='http://10.10.22.201:11434')

# Добавить на сервер модель
client.pull('gemma4:26b')
# client.pull('gemma4:e4b')
# client.pull('qwen2.5:7b')
# client.pull('qwen3.5:4b')
# client.pull('qwen2.5:14b')

# Для проверки в cmd
# curl http://10.10.22.203:11434    - запущен ли сервер с llm
# curl http://10.10.22.203:11434/api/tags   - какие модели доступны


# embeddings
# PARSER_EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
# PARSER_EMBED_MODEL=sergeyzh/LaBSE-ru-sts
# PARSER_EMBED_MODEL=intfloat/multilingual-e5-small
# PARSER_EMBED_MODEL=cointegrated/rubert-tiny2

# model='gemma4:26b'
# messages=[{'role': 'user', 'content': 'Hello!'}]

# response = client.chat(
#     model=model,
#     messages=messages
# )

# print(response.message.content)
