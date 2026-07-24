FROM public.ecr.aws/lambda/python:3.12

COPY requirements-layer.txt .
RUN pip install -r requirements-layer.txt --no-cache-dir

COPY handler.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.handler"]
