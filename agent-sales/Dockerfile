FROM python:3.11-slim

# Ngăn Python ghi file .pyc và bật stdout/stderr unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy dependencies list và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code của agent vào thư mục agent_sales để hỗ trợ ADK import
# Vì folder agent-sales có dấu gạch ngang, ta copy nó vào trong folder agent_sales_pkg bên trong container
# Tuy nhiên, script main.py và run_cli.py có thể xử lý việc này. 
# Cách đơn giản nhất: Đặt toàn bộ code vào /app/agent_sales
COPY . /app/agent_sales

# Thiết lập thư mục làm việc là bên trong package
WORKDIR /app/agent_sales

# Expose port cho FastAPI
EXPOSE 8000

# Chạy server FastAPI qua Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
