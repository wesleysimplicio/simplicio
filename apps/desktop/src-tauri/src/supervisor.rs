use std::time::Duration;

const DEFAULT_MAX_RESTARTS: u8 = 3;
const MAX_BACKOFF_SECONDS: u64 = 30;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SidecarState {
    Stopped,
    Starting { attempt: u8 },
    Healthy,
    Degraded { attempt: u8 },
    Offline,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SidecarSupervisor {
    state: SidecarState,
    failures: u8,
    max_restarts: u8,
    backoff: Duration,
}

impl Default for SidecarSupervisor {
    fn default() -> Self {
        Self::new(DEFAULT_MAX_RESTARTS)
    }
}

impl SidecarSupervisor {
    pub fn new(max_restarts: u8) -> Self {
        Self {
            state: SidecarState::Stopped,
            failures: 0,
            max_restarts,
            backoff: Duration::ZERO,
        }
    }

    pub fn state(&self) -> &SidecarState {
        &self.state
    }

    pub fn begin_start(&mut self) -> bool {
        if self.failures >= self.max_restarts {
            self.state = SidecarState::Offline;
            return false;
        }
        let attempt = self.failures.saturating_add(1);
        self.state = SidecarState::Starting { attempt };
        true
    }

    pub fn mark_healthy(&mut self) {
        self.failures = 0;
        self.backoff = Duration::ZERO;
        self.state = SidecarState::Healthy;
    }

    pub fn mark_failed(&mut self) -> Duration {
        self.failures = self.failures.saturating_add(1);
        let seconds = 2u64.saturating_pow(self.failures.saturating_sub(1) as u32).min(MAX_BACKOFF_SECONDS);
        self.backoff = Duration::from_secs(seconds);
        self.state = if self.failures >= self.max_restarts {
            SidecarState::Offline
        } else {
            SidecarState::Degraded { attempt: self.failures }
        };
        self.backoff
    }

    pub fn restart_allowed(&self) -> bool {
        self.failures < self.max_restarts
    }

    pub fn backoff(&self) -> Duration {
        self.backoff
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn starts_healthy_and_resets_after_recovery() {
        let mut supervisor = SidecarSupervisor::default();
        assert!(supervisor.begin_start());
        assert_eq!(*supervisor.state(), SidecarState::Starting { attempt: 1 });
        supervisor.mark_healthy();
        assert_eq!(*supervisor.state(), SidecarState::Healthy);
        assert_eq!(supervisor.backoff(), Duration::ZERO);
    }

    #[test]
    fn bounds_restarts_and_opens_circuit_after_three_failures() {
        let mut supervisor = SidecarSupervisor::default();
        assert_eq!(supervisor.mark_failed(), Duration::from_secs(1));
        assert!(supervisor.restart_allowed());
        assert_eq!(supervisor.mark_failed(), Duration::from_secs(2));
        assert!(supervisor.restart_allowed());
        assert_eq!(supervisor.mark_failed(), Duration::from_secs(4));
        assert_eq!(*supervisor.state(), SidecarState::Offline);
        assert!(!supervisor.restart_allowed());
        assert!(!supervisor.begin_start());
    }

    #[test]
    fn cannot_accumulate_an_unbounded_backoff() {
        let mut supervisor = SidecarSupervisor::new(20);
        for _ in 0..20 {
            supervisor.mark_failed();
        }
        assert_eq!(supervisor.backoff(), Duration::from_secs(MAX_BACKOFF_SECONDS));
    }
}
