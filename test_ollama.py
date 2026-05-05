import ollama

response = ollama.chat(
    model='llama3.2',
    messages=[{'role': 'user', 'content': 'Say: Jireh is online.'}]
)
print(response['message']['content'])