import json
with open('metadata.json','r',encoding='utf-8') as f:
    d=json.load(f)
print(len(d))
print('last_id=',d[-1].get('id'))
