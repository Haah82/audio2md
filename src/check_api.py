# -*- coding: utf-8 -*-
"""Kiểm tra model Gemini theo key đã cấu hình mà không in credential."""

import argparse
import os
import sys

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

from gemini_pool import configured_keys, redact_error


def _supports_generate(model):
    actions = getattr(model, 'supported_actions', None) or []
    return any(str(action).lower() == 'generatecontent' for action in actions)


def _model_id(model):
    return (getattr(model, 'name', None) or '').removeprefix('models/')


def check(probe=False, env=os.environ, emit=print, client_factory=None):
    """List model theo từng key; probe chỉ chạy khi được yêu cầu rõ ràng."""
    if client_factory is None:
        free, paid = configured_keys(env)
    else:
        free, paid = configured_keys(env, client_factory)
    keys = free + paid
    if not keys:
        emit('[ERROR] Khong tim thay API key Gemini hop le.')
        return 1

    failed = False
    for key in keys:
        try:
            models = [model for model in key.client.models.list() if _supports_generate(model)]
            model_ids = [_model_id(model) for model in models if _model_id(model)]
            emit(f'[CHECK] {key.nhan} | generateContent: {len(model_ids)}')
            for model_id in model_ids:
                status = 'OK'
                if probe:
                    try:
                        response = key.client.models.generate_content(
                            model=model_id,
                            contents='Reply with exactly: OK')
                        status = 'OK' if getattr(response, 'text', None) else 'EMPTY'
                    except Exception as error:
                        status = f'ERROR: {redact_error(error, [key.gia_tri])}'
                        failed = True
                emit(f'  - {model_id} | {status}')
        except Exception as error:
            emit(f'[CHECK] {key.nhan} | ERROR: {redact_error(error, [key.gia_tri])}')
            failed = True
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(
        description='List Gemini models. --probe sends a minimal text request and may consume quota.')
    parser.add_argument('--probe', action='store_true',
                        help='Gui request text toi thieu cho tung model generateContent.')
    args = parser.parse_args()
    return check(probe=args.probe)


if __name__ == '__main__':
    sys.exit(main())
