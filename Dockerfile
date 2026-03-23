echo FROM python:3.9-slim > Dockerfile
echo WORKDIR /usr/src/app >> Dockerfile
echo COPY happy.py . >> Dockerfile
echo CMD ["python", "happy.py"] >> Dockerfile