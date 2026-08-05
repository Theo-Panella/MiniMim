FROM python:3

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

VOLUME C:\temp\log_para_teste.txt

CMD [ "/bin/bash" ]
