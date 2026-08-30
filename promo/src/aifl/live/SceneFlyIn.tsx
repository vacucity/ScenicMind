import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { PageCam, type CamKey } from './PageCam';
import layout from '../live-layout.json';

const cards = layout.projects.cards;
const AMBER = '#c58b35';
const pileX = 1510;
const pileY = 210;
const keys: CamKey[] = [
  { frame: 0, cx: pileX, cy: pileY, zoom: 2.15, rotX: 42, rotY: -28, rotZ: 7, persp: 1100 },
  { frame: 34, cx: pileX, cy: pileY, zoom: 1.95, rotX: 38, rotY: 24, rotZ: -5, persp: 1100 },
  { frame: 62, cx: 960, cy: 520, zoom: .88, rotX: 12, rotY: 0, rotZ: 0, persp: 1300 },
  { frame: 112, cx: 960, cy: 540, zoom: .92 },
  { frame: 126, cx: 1440, cy: 315, zoom: 1.55 },
  { frame: 174, cx: 1440, cy: 315, zoom: 1.55 },
  { frame: 190, cx: 1100, cy: 490, zoom: 2.0 },
];

export const SceneFlyIn: React.FC = () => {
  const frame = useCurrentFrame();
  const select = interpolate(frame, [150, 164], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  return <AbsoluteFill>
    <PageCam src="textures/live/projects-empty.png" pageH={1080} keys={keys} ease={Easing.bezier(.33, 0, .15, 1)}>
      {frame < 58 ? <div style={{ position: 'absolute', left: -2800, top: -2800, width: 7600, height: 7600, opacity: interpolate(frame, [34, 58], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }), background: 'radial-gradient(900px 650px at 58% 42%, rgba(197,139,53,.22), transparent 68%), repeating-linear-gradient(100deg,rgba(255,255,255,.03) 0 1px,transparent 2px 8px),linear-gradient(115deg,#1f2926,#35433e 35%,#17211e)' }} /> : null}
      <Img src={staticFile('textures/live/projects-30d-empty.png')} style={{ position: 'absolute', inset: 0, width: 1920, height: 1080, opacity: select }} />
      {cards.map((card, i) => {
        const cue = 36 + i * 4 - .18 * i * i;
        const fly = interpolate(frame, [cue, cue + 14], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.3, 0, .2, 1) });
        const settle = interpolate(frame, [cue + 10, cue + 16], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.3, 0, .25, 1.15) });
        const px = pileX + ((i * 11) % 7 - 3) * 3;
        const py = pileY + ((i * 7) % 5 - 2) * 3;
        const dx = (px - card.x) * (1 - fly);
        const dy = (py - card.y) * (1 - fly);
        const z = (52 - i * 3) * (1 - fly) + Math.sin(fly * Math.PI) * 90 * (1 - settle);
        return <div key={card.file} style={{ position: 'absolute', left: card.x, top: card.y, width: card.w, height: card.h, borderRadius: 12, overflow: 'hidden', transform: `translate3d(${dx}px,${dy}px,${z}px) rotateZ(${((i * 13) % 7 - 3) * (1 - fly)}deg) scale(${1 + Math.sin(fly * Math.PI) * .055})`, boxShadow: fly < .99 ? '0 28px 64px rgba(8,38,29,.28)' : '0 2px 8px rgba(8,38,29,.08)' }}>
          <Img src={staticFile(`textures/live/${card.file}`)} style={{ width: '100%', height: '100%' }} />
        </div>;
      })}
      {frame >= 124 ? <>
        {[0, 1].map((r) => <div key={r} style={{ position: 'absolute', left: 1488 - (18 + select * (38 + r * 20)), top: 313 - (18 + select * (38 + r * 20)), width: 2 * (18 + select * (38 + r * 20)), height: 2 * (18 + select * (38 + r * 20)), borderRadius: '50%', border: `2px solid ${AMBER}`, opacity: frame > 150 ? 1 - select : 0 }} />)}
      </> : null}
    </PageCam>
  </AbsoluteFill>;
};
