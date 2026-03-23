Run docker build -t my-agent .
#0 building with "default" instance using docker driver

#1 [internal] load build definition from Dockerfile
#1 transferring dockerfile: 198B 0.0s done
#1 DONE 0.0s
Dockerfile:1
--------------------
   1 | >>> echo FROM python:3.9-slim > Dockerfile
   2 |     echo WORKDIR /usr/src/app >> Dockerfile
   3 |     echo COPY happy.py . >> Dockerfile
--------------------
ERROR: failed to build: failed to solve: dockerfile parse error on line 1: unknown instruction: echo
Error: Process completed with exit code 1.
