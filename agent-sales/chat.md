PS F:\ANHTHU\1-HCMUS\CONTEST\SEAHACKATHON\ai-service> python agent-sales/run_cli.py
10:09:21 - LiteLLM:WARNING: common_utils.py:979 - litellm: could not pre-load bedrock-runtime response stream shape — Bedrock event-stream decoding will be unavailable. Error: No module named 'botocore'
10:09:23 - LiteLLM:WARNING: common_utils.py:24 - litellm: could not pre-load sagemaker-runtime response stream shape — SageMaker event-stream decoding will be unavailable. Error: No module named 'botocore'
⏳ Đang khởi tạo Sales Agent...
✅ Agent 'sales_closing_agent' loaded with tools: ['save_order_info', 'get_order_status', 'confirm_order']

============================================================
🛍️  SALES CLOSING AGENT — Trợ lý chốt đơn hàng
============================================================
💬 Nhập tin nhắn để chat với agent.
📝 Thử nói: 'em muốn mua' để bắt đầu flow chốt đơn.
🔄 Gõ 'reset' để bắt đầu phiên mới.
🚪 Gõ 'quit' hoặc Ctrl+C để thoát.
------------------------------------------------------------

👤 Bạn: alo

🤖 Agent: Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY.

⚠️  Gemini API đã hết quota (429).
🔄 Tự động chuyển đổi sang Fallback Agent...

🤖 Agent (Fallback): Chào bạn yêu quý của mình! 📣 Có bạn vào xem livestream kìa! Alo alo, bạn ơi, bạn đang tìm sản phẩm gì hôm nay ạ? 👋

Mình là Trợ lý Sales AI, sẵn sàng tư vấn cho bạn những sản phẩm hot nhất bên mình. Bạn muốn mua sắm gì hôm nay thì cứ nhắn thoải mái nha! 💛

👤 Bạn: tui muốn mua hàng

🤖 Agent: Event from an unknown agent: sales_closing_agent_fallback, event id: cbf3d152-557d-4abb-a3d7-db6a2870a9b6
Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY.

⚠️  Gemini API đã hết quota (429).
🔄 Tự động chuyển đổi sang Fallback Agent...

🤖 Agent (Fallback): Dạ dạ, có khách muốn mua hàng rồi nè! 🎉 Chào bạn yêu quý, bạn muốn mua sản phẩm nào ạ? Bên 
mình có nhiều mẫu lắm, bạn thích gì cứ nói mình tư vấn ngay cho nha! 🛍️

👤 Bạn: lấy 1 bộ sản phẩm best seller cho tui nha

🤖 Agent: Event from an unknown agent: sales_closing_agent_fallback, event id: 0848180b-0b32-462b-b839-ec0d403f9d77
Event from an unknown agent: sales_closing_agent_fallback, event id: cbf3d152-557d-4abb-a3d7-db6a2870a9b6        
Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY.

⚠️  Gemini API đã hết quota (429).
🔄 Tự động chuyển đổi sang Fallback Agent...

🤖 Agent (Fallback): Dạ có khách muốn lấy bộ best seller nèeee! 🔥

Mình cảm ơn bạn đã quan tâm nha! Nhưng mà bên mình đang có nhiều sản phẩm best seller lắm ạ: bộ kem dưỡng trắng da, bộ trị mụn, bộ chống lão hóa, bộ dưỡng tóc, ... Bạn cho mình biết rõ hơn bạn đang tìm dòng sản phẩm nào để mình tư vấn kỹ hơn nha! 🥰

Hay bạn để mình giới thiệu sơ qua vài bộ best seller đang hot nhất bên mình cho bạn tham khảo ạ?

👤 Bạn: trị mụn

🤖 Agent: Event from an unknown agent: sales_closing_agent_fallback, event id: afb7f71f-bf41-439f-a46f-e83e4ddd9b30
Event from an unknown agent: sales_closing_agent_fallback, event id: 0848180b-0b32-462b-b839-ec0d403f9d77        
Event from an unknown agent: sales_closing_agent_fallback, event id: cbf3d152-557d-4abb-a3d7-db6a2870a9b6        
Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY.

⚠️  Gemini API đã hết quota (429).
🔄 Tự động chuyển đổi sang Fallback Agent...

🤖 Agent (Fallback): Dạ bộ trị mụn best seller bên mình đang có giá siêu tốt chỉ **399k** thôi ạ! 🥳 Bạn đồng ý với mức giá này không nè?

Với lại, bạn cho mình xin thêm thông tin để hoàn thiện đơn hàng nha — cho mình xin **địa chỉ giao hàng** và **số 
điện thoại** để bên mình giao cho bạn nhanh nhất nhé! 🚚💨

👤 Bạn: 0348030141, tân hưng quận 7 nha em iu

🤖 Agent: Event from an unknown agent: sales_closing_agent_fallback, event id: fe434df2-6ed5-4a65-a2f9-670efd611725
Event from an unknown agent: sales_closing_agent_fallback, event id: c5387dfa-4fd0-45fd-b557-ebab7df62aa8        
Event from an unknown agent: sales_closing_agent_fallback, event id: 076b69f1-d4a9-4bfc-b34d-6b26ea144bf6        
Event from an unknown agent: sales_closing_agent_fallback, event id: afb7f71f-bf41-439f-a46f-e83e4ddd9b30        
Event from an unknown agent: sales_closing_agent_fallback, event id: 0848180b-0b32-462b-b839-ec0d403f9d77        
Event from an unknown agent: sales_closing_agent_fallback, event id: cbf3d152-557d-4abb-a3d7-db6a2870a9b6        
Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY.
Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x000002503F1F4530>
Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x000002503F488D10>
Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x000002503F4C4620>
Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x000002503F4C6E10>

⚠️  Gemini API đã hết quota (429).
🔄 Tự động chuyển đổi sang Fallback Agent...

🤖 Agent (Fallback): Dạ em tổng kết lại đơn hàng của mình nha:

- 🛍️ **Sản phẩm:** Bộ trị mụn best seller
- 📦 **Số lượng:** 1
- 💰 **Giá:** 399k
- 📍 **Địa chỉ:** Tân Hưng, Quận 7
- 📱 **SĐT:** 0348030141

Anh/chị xác nhận đồng ý với giá **399k** thì "chốt đơn" luôn cho em nha! 🎉

👤 Bạn: