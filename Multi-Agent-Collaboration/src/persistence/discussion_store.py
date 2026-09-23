from pathlib import Path
import json
from src.state.discussion_state import DiscussionState

store_dir = Path("data/discussions")
export_dir = Path("data/exports")


class DiscussionStore:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else store_dir

    def _get_path(self, discussion_id, directory=None):
        folder = Path(directory) if directory else self.base_dir
        return folder / f"{discussion_id}.json"

    def save(self, state, directory=None, indent=2):
        if not state.discussion_id:
            raise ValueError("Cannot save discussion with empty discussion_id.")

        folder = Path(directory) if directory else self.base_dir
        folder.mkdir(parents=True, exist_ok=True)

        file_path = self._get_path(state.discussion_id, folder)
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")

        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=indent)
            temp_path.replace(file_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

        return file_path

    def load(self, discussion_id, directory=None):
        file_path = self._get_path(discussion_id, directory)
        if not file_path.exists():
            raise FileNotFoundError(f"Discussion {discussion_id} not found at {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted discussion file for {discussion_id}: {e}")

        return DiscussionState.from_dict(data)

    def exists(self, discussion_id, directory=None):
        return self._get_path(discussion_id, directory).exists()

    def delete(self, discussion_id, directory=None):
        file_path = self._get_path(discussion_id, directory)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_discussions(self, directory=None):
        folder = Path(directory) if directory else self.base_dir
        if not folder.exists():
            return []

        results = []
        for file in folder.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append({
                    "discussion_id": data.get("discussion_id", file.stem),
                    "topic": data.get("topic", ""),
                    "status": data.get("status", "unknown"),
                    "current_round": data.get("current_round", 0),
                    "num_rounds": data.get("num_rounds", 0),
                    "participants": data.get("participants", []),
                    "message_count": len(data.get("messages", [])),
                    "opinions_count": sum(len(ops) for ops in data.get("opinions", {}).values()),
                    "retrievals_count": len(data.get("retrieval_events", [])),
                    "started_at": data.get("started_at", ""),
                    "completed_at": data.get("completed_at"),
                    "file_path": str(file),
                })
            except Exception:
                continue

        results.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return results

    def export_for_week4(self, target, output_path=None, indent=2):
        state = self.load(target) if isinstance(target, str) else target

        rounds_data = {}
        for r in range(1, max(state.num_rounds, state.current_round) + 1):
            rounds_data[f"round_{r}"] = [m.as_dict() for m in state.get_round_messages(r)]

        week4_payload = {
            "schema_version": "week4.v1",
            "discussion_id": state.discussion_id,
            "topic": state.topic,
            "participants": state.participants,
            "graph": state.graph_config,
            "num_rounds": state.num_rounds,
            "current_round": state.current_round,
            "status": state.status.value,
            "started_at": state.started_at,
            "completed_at": state.completed_at,
            "termination_reason": state.termination_reason,
            "rounds": rounds_data,
            "retrieval_events": state.retrieval_events,
            "opinion_history": state.opinions,
            "checkpoints": state.checkpoints,
            "metadata": state.metadata,
        }

        out_file = Path(output_path) if output_path else export_dir / f"week4_{state.discussion_id}.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(week4_payload, f, indent=indent)

        return out_file
