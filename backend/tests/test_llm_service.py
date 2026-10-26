"""Offline contract tests; never read local keys or contact a provider."""

import builtins
from dataclasses import replace
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

# Import the service configuration without loading the user's backend/.env.
with patch("dotenv.load_dotenv"), patch.dict(os.environ, {}, clear=True):
    from app.services import llm_service as router
    from app.services import llm_common as common
    from app.services import openai_service, claude_service

PROVIDERS = (openai_service, claude_service)
OPERATIONS = router.__all__


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.config = patch.object(router, "settings", replace(router.settings, llm_provider="openai"))
        self.config.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.config.stop)

    def test_same_public_contract(self):
        for operation in OPERATIONS:
            signatures = [inspect.signature(getattr(m, operation))
                          for m in (router, *PROVIDERS)]
            self.assertEqual(signatures[0], signatures[1])
            self.assertEqual(signatures[0], signatures[2])

    def test_only_openai(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai'
        with patch.object(openai_service, 'generate_reply', return_value='GPT') as call:
            self.assertEqual(router.generate_reply('hello', 'board'), 'GPT')
            call.assert_called_once_with('hello', 'board')

    def test_only_claude_and_alias(self):
        for key in ('ANTHROPIC_API_KEY', 'CLAUDE_API_KEY'):
            with self.subTest(key=key), patch.dict(os.environ, {key: 'test-claude'}, clear=True):
                with patch.object(claude_service, 'generate_reply', return_value='Claude') as call:
                    self.assertEqual(router.generate_reply('hello', 'board'), 'Claude')
                    call.assert_called_once()

    def test_no_keys_fails_for_every_operation(self):
        args = [('question', 'context'), ('image.png', 'file'), ('question', 'analysis'),
                ('question', 'target', [], 'image.png')]
        for operation, arguments in zip(OPERATIONS, args):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, r'backend/\.env'):
                    getattr(router, operation)(*arguments)

    def test_both_keys_preference_and_fallback_for_every_operation(self):
        os.environ.update(OPENAI_API_KEY='test-openai', ANTHROPIC_API_KEY='test-claude')
        args = [('q', 'c'), ('i.png', 'f'), ('q', 'a'), ('q', 't', [], 'i.png')]
        for preference in ('openai', 'claude', 'anthropic'):
            first, second = PROVIDERS if preference == 'openai' else PROVIDERS[::-1]
            with patch.object(router, 'settings', replace(router.settings, llm_provider=preference)):
                for operation, arguments in zip(OPERATIONS, args):
                    with self.subTest(preference=preference, operation=operation):
                        with patch.object(first, operation, return_value='first') as primary, \
                             patch.object(second, operation, return_value='second') as fallback:
                            self.assertEqual(getattr(router, operation)(*arguments), 'first')
                            fallback.assert_not_called()
                            primary.side_effect = RuntimeError('simulated API failure')
                            with self.assertLogs(router.logger, level='WARNING') as logs:
                                self.assertEqual(getattr(router, operation)(*arguments), 'second')
                            self.assertIn('retrying', logs.output[0])
                            fallback.assert_called_once_with(*arguments)

    def test_single_provider_error_propagates(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai'
        with patch.object(openai_service, 'generate_reply', side_effect=RuntimeError('failed')):
            with self.assertRaisesRegex(RuntimeError, 'failed'):
                router.generate_reply('q', 'c')

    def test_both_fail_propagates_second_error(self):
        os.environ.update(OPENAI_API_KEY='test-openai', CLAUDE_API_KEY='test-claude')
        with patch.object(openai_service, 'generate_reply', side_effect=RuntimeError('primary')), \
             patch.object(claude_service, 'generate_reply', side_effect=ValueError('secondary')), \
             self.assertLogs(router.logger, level='WARNING'):
            with self.assertRaisesRegex(ValueError, 'secondary'):
                router.generate_reply('q', 'c')

    def test_missing_sdk_falls_back(self):
        os.environ.update(OPENAI_API_KEY='test-openai', ANTHROPIC_API_KEY='test-claude')
        original_import = builtins.__import__
        def import_without_openai(name, *args, **kwargs):
            if name == 'openai':
                raise ModuleNotFoundError('simulated missing OpenAI SDK')
            return original_import(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=import_without_openai), \
             patch.object(claude_service, 'generate_reply', return_value='Claude'), \
             self.assertLogs(router.logger, level='WARNING'):
            self.assertEqual(router.generate_reply('q', 'c'), 'Claude')

    def test_invalid_preference(self):
        os.environ.update(OPENAI_API_KEY='test-openai', ANTHROPIC_API_KEY='test-claude')
        with patch.object(router, 'settings', replace(router.settings, llm_provider='unknown')):
            with self.assertRaisesRegex(ValueError, 'LLM_PROVIDER'):
                router.generate_reply('q', 'c')

    def test_import_needs_neither_sdk_nor_key(self):
        code = '''
import builtins
original = builtins.__import__
def blocked(name, *args, **kwargs):
    if name in ('openai', 'anthropic'):
        raise AssertionError('Eager SDK import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = blocked
from app.services import llm_service, openai_service, claude_service
try:
    llm_service.generate_reply('q', 'c')
except ValueError as error:
    assert 'backend/.env' in str(error)
else:
    raise AssertionError('Expected missing-key error')
'''
        env = {**os.environ, 'OPENAI_API_KEY': '', 'ANTHROPIC_API_KEY': '', 'CLAUDE_API_KEY': '',
               'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
        result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / 'image.png'
        self.image.write_bytes(b'test image bytes')
        self.cache = patch.object(common, 'IMAGE_ANALYSIS_DIR', self.root / 'cache')
        self.cache.start()
        self.addCleanup(self.cache.stop)

    def response(self, text):
        return SimpleNamespace(
            id='response-test', _request_id='request-test', usage=None, status='completed',
            output_text=text, stop_reason='end_turn',
            content=[SimpleNamespace(type='text', text=text)],
        )

    def mocked_client(self, provider, response):
        client = MagicMock()
        client.__enter__.return_value = client
        endpoint = client.responses if provider is openai_service else client.messages
        endpoint.create.return_value = response
        return client, endpoint.create

    def test_text_image_json_prompts_payloads_and_logs(self):
        payloads = []
        detections = [{'bbox': [0, 0, 10, 10], 'label': 'face', 'score': 0.9}]
        for provider in PROVIDERS:
            name = 'openai' if provider is openai_service else 'claude'
            log = self.root / f'{name}.jsonl'
            client, create = self.mocked_client(provider, self.response('reply'))
            with patch.object(provider, 'get_client', return_value=client), patch.object(provider, 'LOG_FILE', log):
                self.assertEqual(provider.generate_reply('hello', 'board'), 'reply')
                text_payload = create.call_args.kwargs
                self.assertEqual(provider.analyze_inserted_image(str(self.image), 'file'), 'reply')
                image_payload = create.call_args.kwargs
                before = create.call_count
                self.assertEqual(provider.analyze_inserted_image(str(self.image), 'file'), 'reply')
                self.assertEqual(create.call_count, before)
                create.return_value = self.response('```json\n{"action":"circle","target_description":"face"}\n```')
                self.assertEqual(provider.extract_visual_target('circle face', 'a face'),
                                 {'action': 'circle', 'target_description': 'face'})
                target_payload = create.call_args.kwargs
                create.return_value = self.response('{"candidate_index":0}')
                self.assertEqual(provider.select_visual_candidate('circle face', 'face', detections, str(self.image)),
                                 {**detections[0], 'candidate_index': 0})
                candidate_payload = create.call_args.kwargs
            entries = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([e['operation'] for e in entries], OPERATIONS)
            self.assertTrue(all(e['provider'] == name for e in entries))
            self.assertTrue(all(e['request']['model'] == provider._model() for e in entries))
            if name == 'openai':
                content = image_payload['input'][0]['content']
                self.assertEqual(content[1]['type'], 'input_image')
                self.assertTrue(content[1]['image_url'].startswith('data:image/png;base64,'))
                self.assertEqual(target_payload['instructions'], common.TARGET_SYSTEM)
                self.assertEqual(candidate_payload['instructions'], common.CANDIDATE_SYSTEM)
            else:
                content = image_payload['messages'][0]['content']
                self.assertEqual(content[1]['type'], 'image')
                self.assertEqual(content[1]['source']['media_type'], 'image/png')
                self.assertEqual(target_payload['system'], common.TARGET_SYSTEM)
                self.assertEqual(candidate_payload['system'], common.CANDIDATE_SYSTEM)
            payloads.append([e['request']['input'] for e in entries])
        self.assertEqual(payloads[0], payloads[1])
        self.assertTrue((self.root / 'cache/openai/file.json').exists())
        self.assertTrue((self.root / 'cache/claude/file.json').exists())

    def test_bad_json_and_candidate_indices_raise(self):
        for provider in PROVIDERS:
            with patch.object(provider, '_request') as request:
                for raw in ('not json', '[]', '{"action": 1, "target_description": "face"}', '{}'):
                    request.return_value = raw
                    with self.assertRaises(ValueError):
                        provider.extract_visual_target('q', 'a')
                for index in (-1, 1, True, '0', None):
                    request.return_value = json.dumps({'candidate_index': index})
                    with self.assertRaises(ValueError):
                        provider.select_visual_candidate('q', 't', [
                            {'bbox': [0, 0, 1, 1], 'label': 'face', 'score': 0.9}
                        ], str(self.image))

    def test_feeling_label_contract_for_both_providers(self):
        for provider in PROVIDERS:
            with patch.object(provider, '_request') as request:
                request.return_value = json.dumps({
                    'action': 'circle', 'target_description': 'sad face', 'label': ' sad ',
                })
                self.assertEqual(provider.extract_visual_target('circle sad', 'chart')['label'], 'SAD')
                request.return_value = json.dumps({
                    'action': 'circle', 'target_description': 'sad face', 'label': 2,
                })
                with self.assertRaisesRegex(ValueError, 'label'):
                    provider.extract_visual_target('circle sad', 'chart')

    def test_incomplete_or_empty_responses_raise(self):
        for provider in PROVIDERS:
            response = self.response('')
            client, create = self.mocked_client(provider, response)
            with patch.object(provider, 'get_client', return_value=client):
                with self.assertRaises(ValueError):
                    provider.generate_reply('q', 'c')
                response.output_text = 'partial'
                response.content[0].text = 'partial'
                response.status = 'incomplete'
                response.stop_reason = 'max_tokens'
                with self.assertRaises(ValueError):
                    provider.generate_reply('q', 'c')

    def test_cache_invalidated_on_model_change(self):
        for provider in PROVIDERS:
            with patch.object(provider, '_request', return_value='analysis') as request, \
                 patch.object(provider, '_model', return_value='first'):
                provider.analyze_inserted_image(str(self.image), 'model-file')
                with patch.object(provider, '_model', return_value='second'):
                    provider.analyze_inserted_image(str(self.image), 'model-file')
                self.assertEqual(request.call_count, 2)

    def test_logging_failure_does_not_retry_successful_call(self):
        with patch.object(Path, 'open', side_effect=OSError('read-only')), \
             self.assertLogs(common.logger, level='WARNING'):
            common.save_response(self.root / 'log', 'openai', 'model', 'generate_reply',
                                 'prompt', '', None, None, self.response('reply'), 'reply')


if __name__ == '__main__':
    unittest.main()
