import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema.exceptions import ValidationError
import ai_paper5_strict as strict


class CLIContractTests(unittest.TestCase):
    def invoke(self,args):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            code=strict.main(args)
        return code,json.loads(out.getvalue())

    def test_every_command_help_and_required_arguments(self):
        parser=strict.build_parser()
        sub=next(a for a in parser._actions if isinstance(a,argparse._SubParsersAction))
        catalog=strict.command_index(parser)
        self.assertEqual(set(catalog["commands"]),set(catalog["parameters"]))
        self.assertEqual(len(sub.choices),24)
        for name,command in sub.choices.items():
            with self.subTest(name=name),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as e: parser.parse_args([name,"--help"])
                self.assertEqual(e.exception.code,0)
                if any(a.required for a in command._actions):
                    with self.assertRaises(SystemExit) as e: parser.parse_args([name])
                    self.assertEqual(e.exception.code,2)

    def test_candidate_output_cannot_overwrite_or_create_native_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/"runs";work=base/"fixture";work.mkdir(parents=True)
            original=work/"staged_topic.json";original.write_text('{"status":"reality"}')
            with patch.object(strict,"RUNS",base),patch.object(strict,"chat_task") as execute:
                for out in (original,work/"s08_topic.json",base/"another"/"cli_outputs"/"task.json"):
                    code,body=self.invoke(["chat-task","--run-id","fixture","--phase","initial","--output",str(out)])
                    self.assertEqual(code,2)
                    self.assertEqual(body["status"],"blocked")
                execute.assert_not_called()
            self.assertEqual(original.read_text(),'{"status":"reality"}')

    def test_safe_new_output_and_schema_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/"runs";out=base/"fixture"/"cli_outputs"/"task.json"
            args=["chat-task","--run-id","fixture","--phase","initial","--output",str(out)]
            with patch.object(strict,"RUNS",base),patch.object(strict,"chat_task",side_effect=ValidationError("invalid schema")):
                code,body=self.invoke(args)
                self.assertEqual(code,2);self.assertFalse(out.exists())
            with patch.object(strict,"RUNS",base),patch.object(strict,"chat_task",return_value={"fixture":True}):
                code,body=self.invoke(args)
                self.assertEqual(code,0)
                self.assertEqual(json.loads(out.read_text()),{"fixture":True})
                self.assertEqual(self.invoke(args)[0],2)

    def test_event_trace_delegated_to_original(self):
        with patch.object(strict,"doctor"),patch.object(strict,"original_call",return_value="fixture") as call:
            code,body=self.invoke(["event-compare","--run-id","fixture","--report","event.json","--events-jsonl","events.jsonl"])
        self.assertEqual(code,0)
        args=call.call_args.args[0]
        self.assertEqual(Path(args[2]),strict.V3_EVENTS)
        self.assertEqual(Path(args[-1]).name,"events.jsonl")
        self.assertEqual(args[-2],"--events-jsonl")


if __name__=="__main__": unittest.main()
