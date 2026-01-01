import { CircuitBreaker } from '../circuit-breaker.js';
import { DEFAULT_GOVERNANCE_CONFIG } from '../types.js';

describe('CircuitBreaker', () => {
  let breaker: CircuitBreaker;

  beforeEach(() => {
    breaker = new CircuitBreaker(DEFAULT_GOVERNANCE_CONFIG);
  });

  describe('isAllowed', () => {
    it('should allow new agents (closed state)', () => {
      expect(breaker.isAllowed('new-agent')).toBe(true);
    });

    it('should block halted agents (open state)', () => {
      breaker.halt('agent1', 'test halt');
      expect(breaker.isAllowed('agent1')).toBe(false);
    });

    it('should allow agents after resume', () => {
      breaker.halt('agent1', 'test halt');
      breaker.resume('agent1');
      expect(breaker.isAllowed('agent1')).toBe(true);
    });
  });

  describe('halt and resume', () => {
    it('should halt an agent with reason', () => {
      breaker.halt('agent1', 'suspicious activity');
      const state = breaker.getState('agent1');
      expect(state.state).toBe('open');
      expect(state.haltReason).toBe('suspicious activity');
    });

    it('should resume a halted agent', () => {
      breaker.halt('agent1', 'test');
      const resumed = breaker.resume('agent1');
      expect(resumed).toBe(true);
      const state = breaker.getState('agent1');
      expect(state.state).toBe('closed');
    });

    it('should return false when resuming an already running agent', () => {
      const resumed = breaker.resume('new-agent');
      expect(resumed).toBe(false);
    });
  });

  describe('failure tracking', () => {
    it('should track failures', () => {
      breaker.recordFailure('agent1');
      const state = breaker.getState('agent1');
      expect(state.failureCount).toBe(1);
    });

    it('should open circuit after max failures', () => {
      const config = { ...DEFAULT_GOVERNANCE_CONFIG, maxFailuresBeforeOpen: 3 };
      breaker = new CircuitBreaker(config);

      breaker.recordFailure('agent1');
      breaker.recordFailure('agent1');
      expect(breaker.isAllowed('agent1')).toBe(true);

      breaker.recordFailure('agent1');
      expect(breaker.isAllowed('agent1')).toBe(false);
    });

    it('should reset failure count on success', () => {
      breaker.recordFailure('agent1');
      breaker.recordFailure('agent1');
      breaker.recordSuccess('agent1');
      const state = breaker.getState('agent1');
      expect(state.failureCount).toBe(0);
    });
  });

  describe('getHaltedAgents', () => {
    it('should return list of halted agents', () => {
      breaker.halt('agent1', 'reason1');
      breaker.halt('agent2', 'reason2');

      const halted = breaker.getHaltedAgents();
      expect(halted).toHaveLength(2);
      expect(halted.map(s => s.agentId)).toContain('agent1');
      expect(halted.map(s => s.agentId)).toContain('agent2');
    });
  });
});
