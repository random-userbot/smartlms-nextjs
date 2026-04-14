'use client';

import React, { useEffect, useRef, useState } from 'react';

interface EngagementCameraProps {
  onFeaturesDetected: (features: any) => void;
  enabled: boolean;
  playing?: boolean;
}

export default function EngagementCamera({ onFeaturesDetected, enabled, playing = true }: EngagementCameraProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const faceMeshRef = useRef<any>(null);
  const animationRef = useRef<number | null>(null);
  const isProcessing = useRef(false);
  const [isLoaded, setIsLoaded] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const enabledRef = useRef(enabled);
  const playingRef = useRef(playing);
  const onFeaturesRef = useRef(onFeaturesDetected);

  // Keep refs in sync with props without triggering effect restarts
  useEffect(() => {
    enabledRef.current = enabled;
    playingRef.current = playing;
    onFeaturesRef.current = onFeaturesDetected;
  }, [enabled, playing, onFeaturesDetected]);

  useEffect(() => {
    // Dynamically load Mediapipe FaceMesh from CDN to bypass Turbopack build-time resolution errors
    const loadScripts = async () => {
      if ((window as any).FaceMesh) {
        setIsLoaded(true);
        return;
      }

      return new Promise<void>((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/face_mesh.js';
        script.async = true;
        script.onload = () => {
          setIsLoaded(true);
          resolve();
        };
        script.onerror = () => reject(new Error('Failed to load FaceMesh engine'));
        document.head.appendChild(script);
      });
    };

    loadScripts();
  }, []);

  useEffect(() => {
    if (!isLoaded) return;

    let isMounted = true;
    const initCamera = async () => {
      setCameraError(null);
      let stream: MediaStream | null = null;
      
      try {
        // Attempt 1: High quality constraints
        try {
          stream = await navigator.mediaDevices.getUserMedia({ 
            video: { width: 640, height: 480, frameRate: 15 } 
          });
        } catch (e) {
          console.warn("Neural Eye: Initial constraints failed, trying fallback...", e);
          // Attempt 2: Basic fallback
          stream = await navigator.mediaDevices.getUserMedia({ video: true });
        }
        
        if (!isMounted) {
          stream?.getTracks().forEach(t => t.stop());
          return;
        }

        if (videoRef.current && stream) {
          videoRef.current.srcObject = stream;
        }

        const FaceMesh = (window as any).FaceMesh;
        if (!FaceMesh) {
          console.error("Neural Eye Error: MediaPipe FaceMesh library not found in window object.");
          setCameraError("Engine Missing");
          return;
        }

        const faceMesh = new FaceMesh({
          locateFile: (file: string) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`,
        });

        faceMesh.setOptions({
          maxNumFaces: 2,
          refineLandmarks: true,
          minDetectionConfidence: 0.5,
          minTrackingConfidence: 0.5,
        });

        faceMesh.onResults((results: any) => {
          if (!isMounted || !enabledRef.current) return;

          const numFaces = results.multiFaceLandmarks ? results.multiFaceLandmarks.length : 0;
          if (numFaces === 0) {
            onFeaturesRef.current({ face_detected: false, num_faces: 0 });
            return;
          }

          const landmarks = results.multiFaceLandmarks[0];
          const leftEye = landmarks[468]; 
          const nose = landmarks[1];
          const leftEar = landmarks[234];
          const rightEar = landmarks[454];
          
          const yaw = nose.x - (leftEar.x + rightEar.x) / 2;
          const pitch = nose.y - (leftEar.y + rightEar.y) / 2;

          const au04_concentration = Math.abs(landmarks[9].y - landmarks[10].y);
          const au12_smile = Math.abs(landmarks[61].x - landmarks[291].x);

          onFeaturesRef.current({
            face_detected: true,
            num_faces: numFaces,
            gaze_score: 1.0 - Math.abs(leftEye.x - 0.5) - Math.abs(leftEye.y - 0.5),
            head_pose_yaw: yaw * 100,
            head_pose_pitch: pitch * 100,
            head_pose_stability: 1.0 - Math.abs(yaw) - Math.abs(pitch),
            au04_brow_lowerer: au04_concentration,
            au12_lip_corner_puller: au12_smile,
            timestamp: Date.now(),
          });
        });

        faceMeshRef.current = faceMesh;

        // Custom loop instead of camera_utils helper
        const processFrame = async () => {
          if (!isMounted || !videoRef.current || !faceMeshRef.current) return;
          
          if (enabledRef.current && playingRef.current && videoRef.current.readyState >= 2 && !isProcessing.current) {
             isProcessing.current = true;
             try {
               await faceMesh.send({ image: videoRef.current });
             } catch (e) {
               console.warn("Frame drop in Neural Eye:", e);
             } finally {
               isProcessing.current = false;
             }
          }
          animationRef.current = requestAnimationFrame(processFrame);
        };

        processFrame();
      } catch (err: any) {
        console.error('Neural Eye initialization failure:', err);
        let msg = "Camera Error";
        
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          msg = "Access Denied";
          alert('Neural Eye Permission Error: Camera access was dismissed. Please enable camera permissions in your browser settings.');
        } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
          msg = "No Camera Found";
        } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
          msg = "Camera in Use";
          alert('Neural Eye Conflict: Your camera is currently being used by another application (like Zoom or Teams). Please close other camera apps and refresh.');
        }
        
        setCameraError(msg);
      }
    };

    initCamera();

    return () => {
      isMounted = false;
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      if (videoRef.current?.srcObject) {
        const tracks = (videoRef.current.srcObject as MediaStream).getTracks();
        tracks.forEach(t => t.stop());
      }
      if (faceMeshRef.current) {
        try {
          faceMeshRef.current.close();
        } catch (e) {
          console.warn("FaceMesh cleanup error:", e);
        }
        faceMeshRef.current = null;
      }
    };
  }, [isLoaded]);

  return (
    <div className="relative w-full h-full bg-black rounded-lg overflow-hidden border border-primary/20">
      <video
        ref={videoRef}
        className={`absolute inset-0 w-full h-full object-cover scale-x-[-1] transition-opacity duration-1000 ${playing ? 'opacity-100' : 'opacity-30'}`}
        playsInline
        muted
        autoPlay
      />
      {!playing && enabled && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40 backdrop-blur-[2px] text-white/60 text-[10px] font-black uppercase tracking-widest animate-pulse">
           Neural Sync Paused
        </div>
      )}
      {!enabled && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm text-white/40 text-[10px] font-black uppercase tracking-widest">
           Calibration Offline
        </div>
      )}
      {enabled && !isLoaded && !cameraError && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-md">
           <div className="w-8 h-8 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
        </div>
      )}
      {cameraError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/90 backdrop-blur-lg p-4 text-center">
           <div className="w-10 h-10 bg-primary/20 rounded-full flex items-center justify-center mb-3">
              <span className="text-primary text-lg font-black">!</span>
           </div>
           <div className="text-[10px] font-black text-white uppercase tracking-widest mb-1">
              {cameraError}
           </div>
           <div className="text-[8px] font-medium text-white/40 uppercase tracking-tighter max-w-[120px]">
              {cameraError === "Camera in Use" ? "Close other apps using camera and refresh" : "Check hardware or permissions"}
           </div>
        </div>
      )}
    </div>
  );
}
