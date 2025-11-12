import requests

url = "http://localhost:8080/jobs"
files = {'file': ('clip_en.wav', open('/app/langid_service/tests/data/golden/en_1.wav', 'rb'), 'audio/wav')}

response = requests.post(url, files=files)
print(response.json())
