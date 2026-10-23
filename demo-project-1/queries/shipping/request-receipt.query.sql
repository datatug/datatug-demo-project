SELECT r.order_id,r.request_id,r.message_id,x.receipt_id,x.received_at FROM requests r JOIN receipts x ON x.request_id=r.request_id AND x.message_id=r.message_id WHERE r.order_id=@order_id
