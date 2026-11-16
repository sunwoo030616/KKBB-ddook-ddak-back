import os,hashlib,xml.etree.ElementTree as ET

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def usage_counts(usage):
    usage=usage or {}
    def count(*keys):
        for key in keys:
            value=usage.get(key)
            if isinstance(value,int) and not isinstance(value,bool):return value
        return None
    details=usage.get('prompt_tokens_details') or usage.get('input_tokens_details') or {}
    return {'input':count('input_tokens','prompt_tokens','inputTokens'), 'output':count('output_tokens','completion_tokens','outputTokens'),
            'cached_input':details.get('cached_tokens')}

def load_keys(config):
    env=os.environ.copy()
    if config:
        for c in ET.parse(config).getroot().iter('configuration'):
            if c.get('name')=='KbAiBackendApplication':
                for n in c.iter('env'):
                    key=n.get('name')
                    if key in ('OPENAI_API_KEY','JEV_AI_API_KEY') and n.get('value') and not env.get(key):
                        env[key]=n.get('value')
    for key in ['OPENAI_API_KEY','JEV_AI_API_KEY']:
        if not env.get(key):raise ValueError('Missing '+key+'; no key values logged')
    return env
