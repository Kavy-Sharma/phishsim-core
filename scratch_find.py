import urllib.request
html = urllib.request.urlopen("http://127.0.0.1:5000").read().decode("utf-8")
idx = html.find("class=\"attack-visual\"")
if idx != -1:
    print(html[idx:idx+1500])
else:
    print("attack-visual class not found")
