cat <<EOF > devin_mini.py
import subprocess

def run_ai_task(code_to_run):
    filename = "ai_task.py"
    with open(filename, "w") as f:
        f.write(code_to_run)
    
    print(f"🛠️ [Devin Mini] 코드를 파일로 저장했습니다: {filename}")
    
    # 생성된 코드를 컨테이너 내부에서 직접 실행
    result = subprocess.run(["python3", filename], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ [성공] 결과:\n", result.stdout)
    else:
        print("❌ [에러 발생] 데빈이 수정을 시작합니다...\n", result.stderr)
        # 여기서 원래는 AI 모델에게 에러 로그를 보내서 수정을 요청하는 로직이 들어갑니다.

# 데빈에게 시킬 작업 (예: 1부터 10까지 제곱수 구하기)
task_code = """
for i in range(1, 11):
    print(f"{i}의 제곱: {i**2}")
"""

run_ai_task(task_code)
EOF