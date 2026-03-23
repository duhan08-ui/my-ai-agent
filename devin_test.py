import datetime

now = datetime.datetime.now()
print(f"--- 데빈 작업 시작 시간: {now} ---")
print("안녕하세요! 저는 도커 컨테이너 안에서 실행되는 미니 데빈입니다.")
print("1부터 10까지 합계는:", sum(range(1, 11)), "입니다.")
