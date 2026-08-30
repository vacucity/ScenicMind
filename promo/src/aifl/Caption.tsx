import { interpolate, useCurrentFrame } from 'remotion';

const SANS = '"Microsoft YaHei", "PingFang SC", system-ui, sans-serif';
const AMBER = 'oklch(52% 0.115 65)';

/** Screen-space narration caption: a mono UI info-strip at the bottom of the
 * frame, led by a small amber square. Fades/rises in over 8 frames and fades
 * out over the last 8 of its window. */
export const Caption: React.FC<{ text: string; duration: number; bottom?: number }> = ({
  text,
  duration,
  bottom = 58,
}) => {
  const frame = useCurrentFrame();
  const inT = interpolate(frame, [0, 8], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const outT = interpolate(frame, [duration - 8, duration], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 16,
        fontFamily: SANS,
        fontSize: 58,
        fontWeight: 700,
        letterSpacing: '0.035em',
        color: 'oklch(45% 0.006 82)',
        opacity: inT * outT,
        transform: `translateY(${(1 - inT) * 8}px)`,
        pointerEvents: 'none',
      }}
    >
      <span style={{ width: 11, height: 11, background: AMBER, display: 'inline-block', flex: '0 0 auto' }} />
      <span style={{ background: 'rgba(243,240,232,.88)', border: '1px solid rgba(16,71,55,.1)', borderRadius: 12, padding: '8px 22px 10px', boxShadow: '0 8px 28px rgba(24,26,27,.10)' }}>{text}</span>
    </div>
  );
};
