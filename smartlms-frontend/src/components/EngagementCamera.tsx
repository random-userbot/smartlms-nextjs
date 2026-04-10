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
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
          video: { width: 640, height: 480, frameRate: 15 } 
        });
        
        if (!isMounted) {
          stream.getTracks().forEach(t => t.stop());
          return;
        }

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }

        const FaceMesh = (window as any).FaceMesh;
        if (!FaceMesh) {
          console.error("Neural Eye Error: MediaPipe FaceMesh library not found in window object.");
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
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          alert('Neural Eye Permission Error: Camera access was dismissed. Please enable camera permissions in your browser settings to allow the biometric engagement tracking to function.');
        } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
          alert('Neural Eye Error: No camera device detected. Engagement tracking will remain offline.');
        }
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
      {enabled && !isLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-md">
           <div className="w-8 h-8 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
        </div>
      )}
    </div>
  );
}
