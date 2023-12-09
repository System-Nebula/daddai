from config.config import Config
from langchain.chains import LLMChain
#from langchain import PromptTemplate, HuggingFaceHub
from langchain.prompts import PromptTemplate
from langchain.llms.huggingface_pipeline import HuggingFacePipeline
from langchain.cache import RedisCache
from langchain.globals import set_llm_cache
import redis

redis_client = redis.Redis.from_url(Config.get_redis())
set_llm_cache(RedisCache(redis_client))

HF_API_TOKEN =  Config.get_hf()
template = """Question: {question}

Answer: Let's think step by step."""

hf = HuggingFacePipeline.from_model_id(
    model_id="microsoft/Orca-2-13b",
    task="text-generation",
    pipeline_kwargs={"max_new_tokens": 10},
)
class Model:
    def modCon(question):
        prompt = PromptTemplate.from_template(template)
        chain = prompt | hf
        return chain.invoke({"question": question})
