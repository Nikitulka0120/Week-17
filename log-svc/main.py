import grpc
from concurrent import futures
from datetime import datetime, timezone
import logs_pb2
import logs_pb2_grpc

logs_storage = []
MAX_LOGS = 1000


class LogServiceServicer(logs_pb2_grpc.LogServiceServicer):

    def SendLog(self, request, context):
        entry = {
            "service": request.service,
            "action": request.action,
            "details": request.details,
            "timestamp": request.timestamp or datetime.now(timezone.utc).isoformat(),
        }
        logs_storage.append(entry)
        if len(logs_storage) > MAX_LOGS:
            logs_storage.pop(0)
        print(f"[LOG] {entry['timestamp']} | {entry['service']} | "
              f"{entry['action']} | {entry['details']}")
        return logs_pb2.LogResponse(ok=True)

    def GetLogs(self, request, context):
        limit = request.limit if request.limit > 0 else 50
        recent = logs_storage[-limit:]
        items = [
            logs_pb2.LogEntry(
                service=e["service"],
                action=e["action"],
                details=e["details"],
                timestamp=e["timestamp"],
            )
            for e in reversed(recent)
        ]
        return logs_pb2.LogList(logs=items)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    logs_pb2_grpc.add_LogServiceServicer_to_server(LogServiceServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("Log Service запущен на порту 50051")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
