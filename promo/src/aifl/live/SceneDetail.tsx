import React from 'react';
import { Easing, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { PageCam, type CamKey } from './PageCam';
import layout from '../live-layout.json';

const rows = layout.detail.rows;
const src = staticFile('textures/live/detail-full.png');
const keys: CamKey[] = [
  { frame: 0, cx: 980, cy: 470, zoom: 1.22 },
  { frame: 75, cx: 980, cy: 790, zoom: 1.08 },
  { frame: 100, cx: 980, cy: 760, zoom: 1.08 },
];

export const SceneDetail: React.FC = () => {
  const frame = useCurrentFrame();
  return <PageCam src="textures/live/detail-full.png" pageH={1080} keys={keys} ease={Easing.bezier(.33, 0, .15, 1)}>
    {rows.map((r, i) => {
      const cue = 12 + i * 8;
      const t = interpolate(frame, [cue, cue + 12], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.3, 0, .25, 1) });
      const seam = interpolate(frame, [cue + 11, cue + 16, cue + 22], [0, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
      if (frame < cue || frame > cue + 18) return null;
      return <React.Fragment key={i}>
        <div style={{ position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, borderRadius: 10, backgroundImage: `url(${src})`, backgroundSize: '1920px 1080px', backgroundPosition: `-${r.x}px -${r.y}px`, transform: `perspective(900px) translateY(${-120 * (1 - t)}px) rotateX(${16 * (1 - t)}deg) scale(${1.06 - .06 * t})`, boxShadow: `0 ${28 * (1 - t)}px ${60 * (1 - t)}px rgba(16,71,55,.25)` }} />
        <div style={{ position: 'absolute', left: r.x + r.w * (1 - seam) / 2, top: r.y + r.h - 2, width: r.w * seam, height: 2, background: '#c58b35', boxShadow: '0 0 8px rgba(197,139,53,.5)' }} />
      </React.Fragment>;
    })}
  </PageCam>;
};
