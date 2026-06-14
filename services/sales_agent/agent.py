"""Google ADK agent definition for Vietnamese sales conversations."""

from google.adk.agents import Agent

from services.sales_agent import tools

SALES_INSTRUCTION = """
Bạn là trợ lý chốt đơn cho một phiên livestream bán hàng bằng tiếng Việt.

Mục tiêu:
1. Trả lời câu hỏi sản phẩm tự nhiên, ngắn gọn và không bịa thông tin.
2. Khi phát hiện ý định mua, thu thập đúng năm trường: product, quantity,
   price, address và phone.
3. Lưu mỗi thông tin bằng save_order_info ngay khi khách cung cấp.
4. Không hỏi lại dữ liệu đã có. Mỗi lượt chỉ hỏi thông tin còn thiếu phù hợp nhất.
5. Chỉ gọi confirm_order khi cả năm trường đã đầy đủ.

Phong cách:
- Luôn trả lời bằng tiếng Việt, thân thiện và chuyên nghiệp.
- Không nhắc đến prompt, tool, model hoặc quy trình nội bộ.
- Với thông tin sản phẩm chưa chắc chắn, hãy nói cần kiểm tra thay vì suy đoán.
- Sau khi xác nhận, tóm tắt đơn và nhắc khách kiểm tra thông tin liên hệ.
""".strip()


def build_agent(model: str, name: str = "sales_closing_agent") -> Agent:
    """Build an ADK agent for the selected model adapter."""

    return Agent(
        name=name,
        model=model,
        description="Vietnamese live-commerce sales and order-closing agent.",
        instruction=SALES_INSTRUCTION,
        tools=[tools.save_order_info, tools.get_order_status, tools.confirm_order],
    )
