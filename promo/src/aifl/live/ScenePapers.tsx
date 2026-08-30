import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { PageCam, type CamKey } from './PageCam';
import { DigitRoll } from '../DigitRoll';
import layout from '../live-layout.json';

const cards = layout.papers.cards;
const cues = [18, 34, 50, 66];
const keys: CamKey[] = [
  { frame: 0, cx: 1030, cy: 320, zoom: 1.25 },
  { frame: 42, cx: 1050, cy: 430, zoom: 1.08 },
  { frame: 82, cx: 980, cy: 570, zoom: .94 },
  { frame: 105, cx: 980, cy: 570, zoom: .94 },
];

export const ScenePapers: React.FC = () => {
  const frame = useCurrentFrame();
  const count = cues.filter((cue) => frame >= cue + 22).length;
  const glazeX = interpolate(frame, [84, 98], [-600, 2300], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.45, 0, .35, 1) });
  return <AbsoluteFill>
    <PageCam src="textures/live/papers-full.png" pageH={1080} keys={keys} ease={Easing.bezier(.33, 0, .15, 1)}>
      {cards.map((card, i) => {
        const cue = cues[i];
        const t = interpolate(frame, [cue, cue + 22], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.45, .05, .25, 1.12) });
        if (t <= 0) return <div key={`slot-${i}`} style={{ position: 'absolute', left: card.x - 4, top: card.y - 4, width: card.w + 8, height: card.h + 8, background: '#f8faf8' }} />;
        let press = 0;
        for (let j = i + 1; j < cues.length; j++) press = Math.max(press, interpolate(frame, [cues[j], cues[j] + 4, cues[j] + 8], [0, 7, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }));
        return <div key={card.file} style={{ position: 'absolute', left: card.x, top: card.y, width: card.w, height: card.h, borderRadius: 12, overflow: 'hidden', transform: `translateY(${560 * (1 - t) + press}px) rotate(${(i % 2 ? -2 : 2) * (1 - t)}deg) scale(${1.06 - .06 * t})`, boxShadow: t < .99 ? '0 32px 64px rgba(16,71,55,.24)' : '0 3px 10px rgba(16,71,55,.1)' }}>
          <Img src={staticFile(`textures/live/${card.file}`)} style={{ width: '100%', height: '100%' }} />
        </div>;
      })}
      <div style={{ position: 'absolute', left: glazeX, top: 40, width: 380, height: 1000, transform: 'rotate(14deg)', background: 'linear-gradient(90deg,transparent,rgba(218,239,226,.9),transparent)', mixBlendMode: 'overlay', opacity: frame >= 82 && frame <= 98 ? .65 : 0 }} />
    </PageCam>
    <div style={{ position: 'absolute', right: 90, top: 62, textAlign: 'right', fontFamily: '"Microsoft YaHei",sans-serif', color: '#315f50' }}>
      <div style={{ fontSize: 36, letterSpacing: '.14em' }}>指标蓝图</div>
      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'flex-end' }}><DigitRoll value={String(count * 2)} fontSize={88} color="#c58b35" /></div>
      <div style={{ fontSize: 32, letterSpacing: '.08em' }}>模块自动计算</div>
    </div>
  </AbsoluteFill>;
};
