import subprocess
import sys
import os
import http.client
import json

# 🔒 GitHub Secrets에서 API 키를 가져옵니다.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def ask_gemini_to_fix(filename, error_msg):
    print("🤖 Gemini AI에게 수리를 요청하는 중...")
    
    with open(filename, 'r', encoding='utf-8') as f:
        code = f.read()

    prompt = f"Fix this Python code error. Output only the fixed code without backticks.\n\n[Error]:\n{error_msg}\n\n[Code]:\n{code}"

    conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    })
    headers = {'Content-Type': 'application/json'}
    
    # ⭐ 핵심 변경: 모델명 뒤에 '-latest'를 붙이고 v1beta를 사용합니다.
    # 이 조합이 현재 가장 성공률이 높습니다.
    endpoint = f"/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    
    try:
        conn.request("POST", endpoint, payload, headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))

        if 'candidates' in data:
            fixed_code = data['candidates'][0]['content']['parts'][0]['text']
            return fixed_code.strip().replace("```python", "").replace("```", "")
        else:
            # 🔄 만약 위 모델도 안되면, 구형이지만 안정적인 'gemini-pro'로 마지막 시도
            print("🔄 모델명을 gemini-pro로 변경하여 마지막 시도 중...")
            alt_endpoint = f"/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
            conn.request("POST", alt_endpoint, payload, headers)
            res = conn.getresponse()
            data = json.loads(res.read().decode("utf-8"))
            
            if 'candidates' in data:
                return data['candidates'][0]['content']['parts'][0]['text'].strip().replace("```python", "").replace("```", "")
            else:
                print(f"❌ 모든 모델 호출 실패: {data}")
                sys.exit(1)

    except Exception as e:
        print(f"❌ 시스템 에러: {e}")
        sys.exit(1)

def run_and_fix(filename):
    print(f"🚀 [{filename}] 실행 시도 중...")
    result = subprocess.run([sys.executable, filename], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ 실행 성공! 결과:\n", result.stdout)
    else:
        print("❌ 에러 발생! AI 분석 시작.")
        fixed_code = ask_gemini_to_fix(filename, result.stderr)
        with open(filename, "w", encoding='utf-8') as f:
            f.write(fixed_code)
        print(f"🛠️ {filename} 자가 수리 완료. 재실행 합니다.")
        
        # 다시 실행해서 결과 확인
        final_res = subprocess.run([sys.executable, filename], capture_output=True, text=True)
        print(f"✅ 수리 후 최종 결과: {final_res.stdout if final_res.returncode == 0 else final_res.stderr}")

if __name__ == "__main__":
    with open("happy.py", "w", encoding='utf-8') as f:
        f.write("print('결과는:', 10 / 0)")
    run_and_fix("happy.py")
