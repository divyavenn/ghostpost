import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { Background } from '../components/Background';
import { api, type DesktopDevice } from '../api/client';
import { getAccessToken } from '../lib/supabase';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem;
`;

const Card = styled.div`
  width: 100%;
  max-width: 760px;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(10, 16, 38, 0.85);
  backdrop-filter: blur(10px);
  padding: 2rem;
  color: white;
`;

const Title = styled.h1`
  font-family: 'Fraunces', serif;
  font-size: 2.1rem;
  font-weight: 400;
  margin: 0 0 0.75rem 0;
`;

const Description = styled.p`
  color: rgba(255, 255, 255, 0.78);
  font-family: 'Geist Mono', monospace;
  margin: 0 0 1.2rem 0;
  line-height: 1.55;
`;

const Row = styled.div`
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin: 0.75rem 0 1rem;
`;

const Button = styled.button`
  border: none;
  border-radius: 999px;
  padding: 12px 18px;
  font-family: 'Geist Mono', monospace;
  font-size: 0.95rem;
  cursor: pointer;
  background: #ffffff;
  color: #0a1026;
  font-weight: 600;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
`;

const SecondaryButton = styled(Button)`
  background: rgba(255, 255, 255, 0.12);
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.22);
`;

const LinkButton = styled.a`
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 10px 16px;
  font-family: 'Geist Mono', monospace;
  font-size: 0.88rem;
  border: 1px solid rgba(255, 255, 255, 0.25);
  color: #ffffff;
  text-decoration: none;
  background: rgba(255, 255, 255, 0.08);
`;

const Code = styled.div`
  font-family: 'Geist Mono', monospace;
  font-size: 2rem;
  letter-spacing: 0.22em;
  padding: 0.9rem 1.2rem;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px dashed rgba(255, 255, 255, 0.3);
  width: fit-content;
  margin: 0.6rem 0;
`;

const Status = styled.div<{ $tone?: 'error' | 'success' }>`
  margin-top: 0.7rem;
  font-family: 'Geist Mono', monospace;
  font-size: 0.83rem;
  color: ${({ $tone }) => ($tone === 'error' ? '#ff8b8b' : $tone === 'success' ? '#93f5b4' : 'rgba(255,255,255,0.78)')};
`;

const SectionTitle = styled.h2`
  font-family: 'Geist Mono', monospace;
  font-size: 0.95rem;
  letter-spacing: 0.05em;
  margin: 1.4rem 0 0.5rem;
  color: rgba(255, 255, 255, 0.86);
`;

const DeviceList = styled.ul`
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
`;

const DeviceItem = styled.li`
  font-family: 'Geist Mono', monospace;
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.75);
  padding: 0.38rem 0;
`;

export function InstallDaemon() {
  const navigate = useNavigate();
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pairCode, setPairCode] = useState<string | null>(null);
  const [pairCodeExpiresAt, setPairCodeExpiresAt] = useState<string | null>(null);
  const [links, setLinks] = useState<{ macos: string; windows: string; linux: string; docs: string } | null>(null);
  const [devices, setDevices] = useState<DesktopDevice[]>([]);
  const [twitterHandle, setTwitterHandle] = useState<string | null>(null);
  const [isGeneratingCode, setIsGeneratingCode] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const activeDevices = useMemo(() => devices.filter(device => !device.revoked), [devices]);
  const isReady = Boolean(twitterHandle && activeDevices.length > 0);

  const refreshStatus = useCallback(async (token: string) => {
    const [downloadLinks, deviceResult] = await Promise.all([
      api.getDesktopDownloadLinks(),
      api.getDesktopDevices(token),
    ]);
    setLinks(downloadLinks);
    setDevices(deviceResult.devices || []);
    setTwitterHandle(deviceResult.user_info.twitter_handle || null);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getAccessToken();
      if (!token) {
        navigate('/login');
        return;
      }
      setAccessToken(token);
      await refreshStatus(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load daemon setup');
    } finally {
      setLoading(false);
    }
  }, [navigate, refreshStatus]);

  useEffect(() => {
    load();
  }, [load]);

  const handleGeneratePairCode = async () => {
    if (!accessToken) return;
    setIsGeneratingCode(true);
    setError(null);
    try {
      const result = await api.startDesktopPairing(accessToken, 10);
      setPairCode(result.pair_code);
      setPairCodeExpiresAt(result.expires_at);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate pairing code');
    } finally {
      setIsGeneratingCode(false);
    }
  };

  const handleRefresh = async () => {
    if (!accessToken) return;
    setIsRefreshing(true);
    setError(null);
    try {
      const deviceResult = await api.getDesktopDevices(accessToken);
      const nextDevices = deviceResult.devices || [];
      const nextHandle = deviceResult.user_info.twitter_handle || null;
      setDevices(nextDevices);
      setTwitterHandle(nextHandle);

      const hasActiveDevice = nextDevices.some(device => !device.revoked);
      if (hasActiveDevice && nextHandle) {
        localStorage.setItem('username', nextHandle);
        navigate('/');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh status');
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleContinue = () => {
    if (!isReady || !twitterHandle) return;
    localStorage.setItem('username', twitterHandle);
    navigate('/');
  };

  if (loading) {
    return (
      <Background>
        <Container>
          <Card>
            <Description>Loading daemon setup…</Description>
          </Card>
        </Container>
      </Background>
    );
  }

  return (
    <Background>
      <Container>
        <Card>
          <Title>Install Desktop Daemon</Title>
          <Description>
            Ghostpost now runs scraping and posting from your desktop daemon. Install it, pair it with a short code, and keep it running.
          </Description>

          <SectionTitle>1) Download</SectionTitle>
          <Row>
            {links?.macos && <LinkButton href={links.macos} target="_blank" rel="noreferrer">macOS</LinkButton>}
            {links?.windows && <LinkButton href={links.windows} target="_blank" rel="noreferrer">Windows</LinkButton>}
            {links?.linux && <LinkButton href={links.linux} target="_blank" rel="noreferrer">Linux</LinkButton>}
            {links?.docs && <LinkButton href={links.docs} target="_blank" rel="noreferrer">Setup docs</LinkButton>}
          </Row>

          <SectionTitle>2) Pair Device</SectionTitle>
          <Row>
            <Button onClick={handleGeneratePairCode} disabled={isGeneratingCode}>
              {isGeneratingCode ? 'Generating…' : 'Generate Pairing Code'}
            </Button>
          </Row>
          {pairCode && (
            <>
              <Code>{pairCode}</Code>
              {pairCodeExpiresAt && (
                <Status>Expires: {new Date(pairCodeExpiresAt).toLocaleString()}</Status>
              )}
            </>
          )}

          <SectionTitle>3) Confirm Daemon Status</SectionTitle>
          <Description style={{ marginBottom: '0.5rem' }}>
            Open daemon Settings, paste the code, and log into your social accounts in your browser profile used by daemon.
          </Description>
          <Row>
            <SecondaryButton onClick={handleRefresh} disabled={isRefreshing}>
              {isRefreshing ? 'Refreshing…' : 'I paired my daemon'}
            </SecondaryButton>
            <Button onClick={handleContinue} disabled={!isReady}>
              Continue to Ghostpost
            </Button>
          </Row>

          <Status $tone={isReady ? 'success' : undefined}>
            {isReady
              ? `Ready. Connected as @${twitterHandle}.`
              : activeDevices.length === 0
                ? 'No active paired device found yet.'
                : 'Device paired. Waiting for linked X handle to be available.'}
          </Status>

          {activeDevices.length > 0 && (
            <DeviceList>
              {activeDevices.map(device => (
                <DeviceItem key={device.id}>
                  {device.device_name} · {device.os} · {device.daemon_version}
                </DeviceItem>
              ))}
            </DeviceList>
          )}

          {error && <Status $tone="error">{error}</Status>}
        </Card>
      </Container>
    </Background>
  );
}

export default InstallDaemon;
