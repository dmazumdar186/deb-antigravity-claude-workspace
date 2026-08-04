import { describe, it, expect } from 'vitest';
import { redact, redactDeep, luhnValid } from '../../src/lib/pii.ts';

describe('luhnValid', () => {
  it('accepts a valid card number', () => {
    // 4111 1111 1111 1111 — canonical Visa test number
    expect(luhnValid('4111111111111111')).toBe(true);
    expect(luhnValid('4111 1111 1111 1111')).toBe(true);
    expect(luhnValid('5555555555554444')).toBe(true); // Mastercard test
  });
  it('rejects a random 16-digit string', () => {
    expect(luhnValid('1234567890123456')).toBe(false);
    expect(luhnValid('9999999999999999')).toBe(false);
  });
  it('rejects too-short or too-long', () => {
    expect(luhnValid('411111')).toBe(false);
    expect(luhnValid('41111111111111111111')).toBe(false);
  });
});

describe('redact — single-type', () => {
  it('redacts Aadhaar with spaces and without', () => {
    const r1 = redact('My Aadhaar is 1234 5678 9012.');
    expect(r1.text).toBe('My Aadhaar is [AADHAAR_REDACTED].');
    expect(r1.counts.aadhaar).toBe(1);
    const r2 = redact('Aadhaar: 123456789012');
    expect(r2.text).toBe('Aadhaar: [AADHAAR_REDACTED]');
  });

  it('redacts PAN', () => {
    const r = redact('PAN is ABCDE1234F please note.');
    expect(r.text).toBe('PAN is [PAN_REDACTED] please note.');
    expect(r.counts.pan).toBe(1);
  });

  it('redacts Indian mobile numbers', () => {
    for (const num of ['9876543210', '+919876543210', '91 9876543210', '09876543210']) {
      const r = redact(`Call me at ${num}.`);
      expect(r.text).toContain('[MOBILE_REDACTED]');
      expect(r.counts.mobile_in).toBeGreaterThanOrEqual(1);
    }
  });

  it('does not redact landline / short digit runs', () => {
    const r = redact('Extension is 4321, order 100');
    expect(r.text).toBe('Extension is 4321, order 100');
    expect(r.counts.mobile_in).toBe(0);
  });

  it('redacts a valid Luhn card', () => {
    const r = redact('Card 4111 1111 1111 1111 charged.');
    expect(r.text).toBe('Card [CARD_REDACTED] charged.');
    expect(r.counts.credit_card).toBe(1);
  });

  it('does not redact a random 16-digit run', () => {
    const r = redact('Order 1234567890123456 dispatched.');
    expect(r.text).toContain('1234567890123456');
    expect(r.counts.credit_card).toBe(0);
  });

  it('redacts UPI handles', () => {
    for (const upi of ['debolshop@paytm', 'user.name@okhdfcbank', 'abc-xyz@ybl']) {
      const r = redact(`Send to ${upi}`);
      expect(r.text).toContain('[UPI_REDACTED]');
      expect(r.counts.upi).toBe(1);
    }
  });

  it('redacts email', () => {
    const r = redact('Reach me at foo@example.com.');
    expect(r.text).toBe('Reach me at [EMAIL_REDACTED].');
    expect(r.counts.email).toBe(1);
  });

  it('classifies UPI over email when domain is a UPI provider', () => {
    const r = redact('Payment: name@paytm');
    expect(r.counts.upi).toBe(1);
    expect(r.counts.email).toBe(0);
  });
});

describe('redact — mixed and edge cases', () => {
  it('handles multiple PII types in one string with correct counts', () => {
    const input = 'Aadhaar 1234 5678 9012, PAN ABCDE1234F, mobile 9876543210, card 4111 1111 1111 1111, email a@b.com';
    const r = redact(input);
    expect(r.counts).toEqual({ aadhaar: 1, pan: 1, mobile_in: 1, upi: 0, credit_card: 1, email: 1 });
    expect(r.total).toBe(5);
    expect(r.text).not.toContain('9876543210');
    expect(r.text).not.toContain('ABCDE1234F');
    expect(r.text).not.toContain('4111');
  });

  it('is idempotent on already-redacted text', () => {
    const once = redact('call 9876543210').text;
    const twice = redact(once).text;
    expect(once).toBe(twice);
  });

  it('empty string → empty result', () => {
    expect(redact('').text).toBe('');
    expect(redact('').total).toBe(0);
  });

  it('leaves non-PII text unchanged', () => {
    const s = 'The quick brown fox jumps over the lazy dog.';
    expect(redact(s).text).toBe(s);
    expect(redact(s).total).toBe(0);
  });

  it('does not confuse PAN pattern in the middle of a longer word', () => {
    // PAN requires word boundary — inside a longer alphanumeric run should not match.
    const r = redact('serial XABCDE1234F5');
    // The interior sequence still matches word-boundary PAN if the surrounding chars are not alphanumeric.
    // Since X is a letter, the PAN pattern's leading \b won't match — expect NO redaction.
    expect(r.counts.pan).toBe(0);
  });
});

describe('redactDeep', () => {
  it('walks object + array structures', () => {
    const input = {
      scenario: 'Customer 9876543210 wants refund',
      transcript: [
        { role: 'agent', text: 'Card 4111 1111 1111 1111 was charged twice' },
        { role: 'customer', text: 'PAN ABCDE1234F' },
      ],
      difficulty: 'Beginner',
      turns: 5,
    };
    const r = redactDeep(input);
    expect(r.total).toBe(3);
    expect(r.value.scenario).not.toContain('9876543210');
    expect(r.value.transcript[0].text).not.toContain('4111');
    expect(r.value.transcript[1].text).not.toContain('ABCDE1234F');
    // Non-string fields survive intact.
    expect(r.value.difficulty).toBe('Beginner');
    expect(r.value.turns).toBe(5);
  });

  it('handles null/undefined/nested arrays', () => {
    const r = redactDeep({ a: null, b: undefined, c: [[['no pii here']]] });
    expect(r.total).toBe(0);
    expect(r.value.a).toBeNull();
    expect(r.value.c[0][0][0]).toBe('no pii here');
  });
});
