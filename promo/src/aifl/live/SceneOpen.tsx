import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { PageCam, type CamKey } from './PageCam';
import layout from '../live-layout.json';

const PINE = '#104737';
const AMBER = '#c58b35';
const PAPER = '#f3f0e8';
const SANS = '"Microsoft YaHei", "PingFang SC", system-ui, sans-serif';
const hero = layout.projects.cards[1] ?? layout.projects.cards[0];
const cx = hero.x + hero.w / 2;
const cy = hero.y + hero.h / 2;
const keys: CamKey[] = [
  { frame: 82, cx: 960, cy: 540, zoom: 0.84 },
  { frame: 114, cx: 960, cy: 540, zoom: 0.84 },
  { frame: 132, cx, cy, zoom: 2.15, rotX: 5, rotY: 24, rotZ: 1.5, persp: 1350 },
  { frame: 220, cx, cy, zoom: 2.15, rotX: 5, rotY: 24, rotZ: 1.5, persp: 1350 },
];

export const SceneOpen: React.FC = () => {
  const frame = useCurrentFrame();
  const brandOut = interpolate(frame, [75, 83], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const pageIn = interpolate(frame, [82, 92], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const lock = interpolate(frame, [94, 114, 130], [0, 1, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const rise = interpolate(frame, [130, 142], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.2, 1.25, .3, 1) });
  const reseat = interpolate(frame, [194, 212], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const lift = rise * (1 - reseat);
  const beam = interpolate(frame, [144, 180], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return <AbsoluteFill style={{ background: PAPER }}>
    {frame < 84 ? <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', opacity: brandOut }}>
      <div style={{ position: 'absolute', width: 3, height: 120, background: AMBER, transform: `scaleY(${interpolate(frame, [0, 10], [0, 1], { extrapolateRight: 'clamp' })})` }} />
      <div style={{ position: 'absolute', width: 120, height: 3, background: AMBER, transform: `scaleX(${interpolate(frame, [8, 18], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })})` }} />
      <div style={{ display: 'flex', gap: 8, marginTop: -10 }}>
        {'智景'.split('').map((ch, i) => {
          const t = interpolate(frame, [12 + i * 5, 25 + i * 5], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.2, .75, .3, 1) });
          return <span key={ch} style={{ fontFamily: SANS, fontSize: 164, fontWeight: 800, color: PINE, opacity: t, filter: `blur(${(1 - t) * 8}px)`, transform: `scale(${1.5 - .5 * t})` }}>{ch}</span>;
        })}
      </div>
      <div style={{ position: 'absolute', top: 650, fontFamily: SANS, fontSize: 36, letterSpacing: '.22em', color: '#587368', opacity: interpolate(frame, [28, 43], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) }}>SCENICMIND · 智能景区决策平台</div>
    </AbsoluteFill> : null}
    {frame >= 82 ? <AbsoluteFill style={{ opacity: pageIn }}>
      <PageCam src="textures/live/projects-full.png" pageH={1080} keys={keys} ease={Easing.bezier(.33, 0, .15, 1)}>
        <div style={{ position: 'absolute', left: hero.x - 7, top: hero.y - 7, width: hero.w + 14, height: hero.h + 14, borderRadius: 18, border: `3px solid ${AMBER}`, opacity: lock * (1 - reseat), boxShadow: `0 0 ${48 * lock}px rgba(197,139,53,.45)` }} />
        <div style={{ position: 'absolute', left: hero.x, top: hero.y, width: hero.w, height: hero.h, borderRadius: 14, overflow: 'hidden', transform: `translateZ(${108 * lift}px) translateY(${Math.sin((frame - 142) / 40 * Math.PI * 2) * 4 * lift}px)`, boxShadow: `0 ${40 * lift}px ${90 * lift}px rgba(16,71,55,.28)`, opacity: frame >= 128 ? 1 : 0 }}>
          <Img src={staticFile(hero.file === 'card2.png' ? 'textures/live/card4-hires.png' : `textures/live/${hero.file}`)} style={{ width: '100%', height: '100%' }} />
          <div style={{ position: 'absolute', inset: 0, border: `3px solid rgba(197,139,53,${.75 * Math.sin(beam * Math.PI)})`, borderRadius: 14 }} />
        </div>
      </PageCam>
      <AbsoluteFill style={{ pointerEvents: 'none', background: `radial-gradient(420px 300px at 50% 50%, transparent 20%, rgba(6,36,27,${.32 * lock}) 100%)` }} />
    </AbsoluteFill> : null}
  </AbsoluteFill>;
};
