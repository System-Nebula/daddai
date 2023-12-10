from fsspec import Callback
from config.config import Config
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.cache import RedisCache
from langchain.globals import set_llm_cache
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.llms import LlamaCpp

import redis

redis_client = redis.Redis.from_url(Config.get_redis())
set_llm_cache(RedisCache(redis_client))

#HF_API_TOKEN =  Config.get_hf()

callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])
llm = LlamaCpp(
    model_path = "/mnt/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q5_K_M.gguf",
    temperature = 0,
    max_tokens = 2000,
    top_p =1,
    callback_manager = callback_manager,
    verbose = True,
)
class Model:
    def modCon(q):
        template = """
        Question: {question}
        """
        
        prompt = PromptTemplate(template=template, input_variables=["question"])
        llm_chain = LLMChain(prompt=prompt,llm=llm)
        return llm_chain.run(q)
