import { describe, expect, it } from 'vitest';
import { normalizeAnswerMarkdown } from './AnswerMarkdown';

describe('normalizeAnswerMarkdown', () => {
  it('does not orphan numbered bold section markers', () => {
    const raw =
      '**Phân tích:**\n' +
      '1. **Tính chất hành vi:** Cá độ trái phép.\n' +
      '2. **Hệ quả pháp lý chính:** Có thể bị xử lý hình sự.\n' +
      '3. **Về thuế:** TNCN chỉ là khía cạnh phụ.';
    const out = normalizeAnswerMarkdown(raw);
    expect(out).toContain('1. **Tính chất hành vi:**');
    expect(out).toContain('2. **Hệ quả pháp lý chính:**');
    expect(out).toContain('3. **Về thuế:**');
    expect(out.split('\n').some((l) => l.trim() === '1.')).toBe(false);
    expect(out.split('\n').some((l) => l.trim() === '3.')).toBe(false);
  });

  it('still splits smashed section headers', () => {
    const raw = '**Kết luận:** A. **Phân tích:** B.';
    const out = normalizeAnswerMarkdown(raw);
    expect(out).toContain('**Kết luận:**');
    expect(out).toContain('**Phân tích:**');
    expect(out.indexOf('**Phân tích:**')).toBeGreaterThan(out.indexOf('**Kết luận:**'));
  });
});
