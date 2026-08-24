"""Command-line entry point for the refactored service."""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from .acquisition import BrainCoSource
from .application import ExperimentApplication
from .config import load_config
from .eeg import build_eeg_processor
from .gaze import ReplayGazeProvider, TobiiG3Provider, TobiiGazeFeatureExtractor
from .policy import MultimodalPolicyEngine
from .runtime import EEGAcquisitionWorker, GazeAcquisitionWorker
from .server import ExperimentHTTPServer
from .server.llm_proxy import LLMProxy
from .storage import (
    ExperimentRunManager,
    RunDocumentStore,
    RunEventRecorder,
    RunJsonlRecorder,
    RunPolicyRecorder,
    RunRawEEGRecorder,
)
from .synchronization import MultimodalSynchronizer


def build_application(config_path: Path) -> tuple:
    config = load_config(config_path)
    run_manager = ExperimentRunManager(config.storage.run_dir)
    synchronizer = MultimodalSynchronizer(
        max_eeg_age_ms=config.synchronization.max_eeg_age_ms,
        max_gaze_age_ms=config.synchronization.max_gaze_age_ms,
    )
    application = ExperimentApplication(
        synchronizer=synchronizer,
        policy=MultimodalPolicyEngine(config.policy),
        event_recorder=RunEventRecorder(run_manager),
        policy_recorder=RunPolicyRecorder(run_manager),
        interaction_recorder=RunJsonlRecorder(run_manager, "interactions.jsonl"),
        run_manager=run_manager,
    )
    return config, application


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Realtime BrainCo EEG/gaze policy pipeline")
    parser.add_argument(
        "--config", type=Path, default=Path("configs/development.json"), help="JSON config path"
    )
    parser.add_argument("--brainco", action="store_true", help="Start real BrainCo acquisition")
    parser.add_argument(
        "--legacy-oi-mi",
        type=Path,
        default=Path("../oi-armi/oi-mi"),
        help=argparse.SUPPRESS,
    )
    gaze = parser.add_mutually_exclusive_group()
    gaze.add_argument(
        "--tobii",
        action="store_true",
        help="Start a real Tobii Pro Glasses 3 gaze stream",
    )
    gaze.add_argument(
        "--gaze-replay",
        type=Path,
        default=None,
        help="Replay gaze feature JSONL while real gaze hardware is unavailable",
    )
    parser.add_argument(
        "--gaze-replay-loop",
        action="store_true",
        help="Loop the gaze replay file until the service stops",
    )
    parser.add_argument(
        "--tobii-hostname",
        default=None,
        help="Tobii G3 hostname/serial; defaults to G3_HOSTNAME, then auto-discovery",
    )
    parser.add_argument(
        "--tobii-discovery-timeout",
        type=float,
        default=8.0,
        help="Seconds to wait for Tobii zeroconf discovery",
    )
    parser.add_argument(
        "--tobii-rtsp-transport",
        choices=("tcp", "udp"),
        default="tcp",
        help="Tobii RTP transport; TCP avoids feeding UDP-loss-corrupted video to PyAV",
    )
    parser.add_argument(
        "--tobii-gaze-only",
        action="store_true",
        help="Diagnostic mode: receive gaze without scene video or screen mapping",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config, application = build_application(args.config)
    application.start_session("development", condition=1)
    tobii_provider: Optional[TobiiG3Provider] = None
    if args.tobii:
        hostname = args.tobii_hostname or os.environ.get("G3_HOSTNAME")
        tobii_provider = TobiiG3Provider(
            hostname,
            using_zeroconf=hostname is None,
            discovery_timeout_seconds=args.tobii_discovery_timeout,
            rtsp_transport=args.tobii_rtsp_transport,
            scene_camera=not args.tobii_gaze_only,
            # Keep the acquisition quality gate aligned with the policy gate.
            # Otherwise C2 could reject a 0.50-valid window in the extractor
            # before the policy ever sees it (the old extractor default was 0.60).
            extractor=TobiiGazeFeatureExtractor(
                min_valid_ratio=config.policy.gaze_min_valid_ratio,
            ),
        )
    server = ExperimentHTTPServer(
        application,
        host=config.server.host,
        port=config.server.port,
        document_store=RunDocumentStore(application.run_manager),
        llm_proxy=LLMProxy(config.llm),
        scene_frame_supplier=(
            tobii_provider.latest_scene_frame if tobii_provider is not None else None
        ),
        screen_mapping_supplier=(
            tobii_provider.latest_screen_mapping if tobii_provider is not None else None
        ),
        screen_layout_updater=(
            tobii_provider.update_screen_layout if tobii_provider is not None else None
        ),
        tobii_calibration_supplier=(
            tobii_provider.calibration_status if tobii_provider is not None else None
        ),
        tobii_calibration_starter=(
            tobii_provider.request_calibration if tobii_provider is not None else None
        ),
        question_registry=application.run_manager,
        eeg_acquisition_enabled=args.brainco,
    )
    worker: Optional[EEGAcquisitionWorker] = None
    if args.brainco:
        source = BrainCoSource(
            sampling_rate_hz=config.eeg.sampling_rate_hz,
            acquirer_kwargs=asdict(config.eeg.brainco),
        )
        raw_recorder = RunRawEEGRecorder(
            application.run_manager,
            chunk_seconds=config.storage.raw_eeg_chunk_seconds,
        )
        worker = EEGAcquisitionWorker(
            source,
            application,
            processor=build_eeg_processor(config.eeg),
            raw_recorder=raw_recorder,
        )
        worker.start()
    gaze_worker: Optional[GazeAcquisitionWorker] = None
    if tobii_provider is not None:
        gaze_worker = GazeAcquisitionWorker(
            tobii_provider,
            application,
            session_id="development",
            raw_recorder=RunJsonlRecorder(application.run_manager, "gaze/raw_samples.jsonl"),
        )
        gaze_worker.start()
    elif args.gaze_replay is not None:
        gaze_worker = GazeAcquisitionWorker(
            ReplayGazeProvider(args.gaze_replay, loop=args.gaze_replay_loop),
            application,
            session_id="development",
        )
        gaze_worker.start()
    host, port = server.address[:2]
    print("Recon pipeline")
    print("  Home:       http://%s:%s/" % (host, port))
    print("  Experiment: http://%s:%s/experiment" % (host, port))
    print("  Monitor:    http://%s:%s/monitor" % (host, port))
    print("  Health:     http://%s:%s/api/health" % (host, port))
    print(
        "  EEG:        %s"
        % ("BrainCo realtime" if worker is not None else "disabled (--brainco not supplied)")
    )
    if worker is not None:
        print("  Runs:       %s" % config.storage.run_dir.expanduser().resolve())
    if gaze_worker is not None:
        print(
            "  Gaze:       %s"
            % (
                "Tobii G3 gaze-only diagnostic"
                if args.tobii and args.tobii_gaze_only
                else "Tobii G3 realtime"
                if args.tobii
                else "JSONL replay"
            )
        )
        if args.tobii:
            print("  Recording:  starts when the calibration phase begins")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        if worker is not None:
            worker.stop()
        if gaze_worker is not None:
            gaze_worker.stop()
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
