import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import styled, { css } from 'styled-components';
import { api } from '../api/client';

// Styled Components
const PageContainer = styled.div`
  min-height: 100vh;
  background-color: #020617;
  color: white;
`;

const ContentWrapper = styled.div`
  max-width: 72rem;
  margin: 0 auto;
  padding: 4rem 1rem;
`;

const Header = styled.div`
  text-align: center;
  margin-bottom: 4rem;
`;

const Title = styled(motion.h1)`
  font-size: 2.25rem;
  font-weight: 700;
  margin-bottom: 1rem;

  @media (min-width: 768px) {
    font-size: 3rem;
  }
`;

const Subtitle = styled(motion.p)`
  color: #94a3b8;
  font-size: 1.125rem;
  max-width: 42rem;
  margin: 0 auto;
`;

const ErrorBanner = styled.div`
  margin-bottom: 2rem;
  padding: 1rem;
  background-color: rgba(127, 29, 29, 0.5);
  border: 1px solid #ef4444;
  border-radius: 0.5rem;
  text-align: center;
`;

const CardsGrid = styled.div`
  display: grid;
  gap: 2rem;

  @media (min-width: 768px) {
    grid-template-columns: repeat(3, 1fr);
  }
`;

const CardContainer = styled(motion.div)<{ $tierName: string; $highlight: boolean }>`
  position: relative;
  border-radius: 1rem;
  border: 2px solid;
  background-color: #0f172a;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: all 0.3s ease-out;

  ${({ $tierName, $highlight }) => {
    if ($tierName === 'Trial') {
      return css`
        border-color: #334155;
        &:hover {
          border-color: #64748b;
          box-shadow: 0 25px 50px -12px rgba(51, 65, 85, 0.2);
        }
      `;
    }
    if ($tierName === 'Paid') {
      return css`
        border-color: #0ea5e9;
        ${$highlight && css`
          box-shadow: 0 0 0 2px rgba(14, 165, 233, 0.5);
        `}
        &:hover {
          border-color: #38bdf8;
          box-shadow: 0 25px 50px -12px rgba(14, 165, 233, 0.2);
        }
      `;
    }
    if ($tierName === 'Premium') {
      return css`
        border-color: #a855f7;
        &:hover {
          border-color: #c084fc;
          box-shadow: 0 25px 50px -12px rgba(168, 85, 247, 0.2);
        }
      `;
    }
  }}
`;

const PopularBadge = styled(motion.div)`
  position: absolute;
  top: -1rem;
  left: 50%;
  transform: translateX(-50%);
  background-color: #0ea5e9;
  color: white;
  font-size: 0.875rem;
  font-weight: 600;
  padding: 0.25rem 1rem;
  border-radius: 9999px;
`;

const TierHeader = styled.div`
  margin-bottom: 1.5rem;
`;

const TierName = styled.h3`
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
`;

const PriceWrapper = styled(motion.div)`
  display: flex;
  align-items: baseline;
  gap: 0.25rem;
`;

const Price = styled.span<{ $tierName: string }>`
  font-size: 2.25rem;
  font-weight: 700;

  ${({ $tierName }) => {
    if ($tierName === 'Premium') {
      return css`
        background: linear-gradient(to right, #c084fc, #f472b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      `;
    }
    if ($tierName === 'Paid') {
      return css`
        background: linear-gradient(to right, #38bdf8, #60a5fa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      `;
    }
    return css`
      color: white;
    `;
  }}
`;

const Period = styled.span`
  color: #94a3b8;
`;

const Description = styled.p`
  color: #94a3b8;
  margin-top: 0.5rem;
`;

const FeaturesList = styled.ul`
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
  flex-grow: 1;
`;

const FeatureItem = styled.li`
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
`;

const CheckIcon = styled.span`
  color: #4ade80;
  margin-top: 0.125rem;
`;

const MinusIcon = styled.span`
  color: #64748b;
  margin-top: 0.125rem;
`;

const FeatureText = styled.span`
  color: #cbd5e1;
`;

const LimitationText = styled.span`
  color: #64748b;
`;

const CTAButton = styled.button<{ $tierName: string; $disabled: boolean }>`
  width: 100%;
  padding: 0.75rem 1.5rem;
  border-radius: 0.5rem;
  font-weight: 600;
  transition: all 0.2s;
  border: none;
  cursor: pointer;

  ${({ $tierName, $disabled }) => {
    if ($disabled) {
      return css`
        background-color: #1e293b;
        color: #64748b;
        cursor: not-allowed;
      `;
    }
    if ($tierName === 'Paid') {
      return css`
        background-color: #0284c7;
        color: white;
        &:hover {
          background-color: #0ea5e9;
        }
      `;
    }
    if ($tierName === 'Premium') {
      return css`
        background-color: #9333ea;
        color: white;
        &:hover {
          background-color: #a855f7;
        }
      `;
    }
    return css`
      background-color: #1e293b;
      color: white;
      &:hover {
        background-color: #334155;
      }
    `;
  }}
`;

const BackLink = styled.div`
  text-align: center;
  margin-top: 3rem;
`;

const BackButton = styled.button`
  color: #94a3b8;
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.2s;

  &:hover {
    color: white;
  }
`;

// Modal Styles
const ModalOverlay = styled(motion.div)`
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
`;

const ModalContent = styled(motion.div)`
  background-color: #0f172a;
  border: 1px solid #7c3aed;
  border-radius: 0.75rem;
  padding: 2rem;
  max-width: 28rem;
  margin: 0 1rem;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  width: 100%;
`;

const ModalTitle = styled.h2`
  font-size: 1.5rem;
  font-weight: 600;
  color: white;
  margin-bottom: 0.5rem;
`;

const ModalSubtitle = styled.p`
  color: #94a3b8;
`;

const FormGroup = styled.div`
  margin-bottom: 1rem;
`;

const Label = styled.label`
  display: block;
  font-size: 0.875rem;
  color: #94a3b8;
  margin-bottom: 0.25rem;
`;

const Required = styled.span`
  color: #f87171;
`;

const Input = styled.input`
  width: 100%;
  padding: 0.75rem 1rem;
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 0.5rem;
  color: white;
  transition: border-color 0.2s;

  &::placeholder {
    color: #64748b;
  }

  &:focus {
    outline: none;
    border-color: #a855f7;
  }
`;

const ButtonRow = styled.div`
  display: flex;
  gap: 0.75rem;
`;

const CancelButton = styled.button`
  flex: 1;
  padding: 0.75rem 1.5rem;
  background-color: #1e293b;
  color: white;
  border: none;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background-color 0.2s;

  &:hover {
    background-color: #334155;
  }
`;

const SubmitButton = styled.button<{ $disabled: boolean }>`
  flex: 1;
  padding: 0.75rem 1.5rem;
  background-color: #7c3aed;
  color: white;
  border: none;
  border-radius: 0.5rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;

  ${({ $disabled }) => $disabled && css`
    opacity: 0.5;
    cursor: not-allowed;
  `}

  &:hover:not(:disabled) {
    background-color: #9333ea;
  }
`;

const SuccessIcon = styled.div`
  font-size: 3rem;
  margin-bottom: 1rem;
  color: #4ade80;
`;

const CloseButton = styled.button`
  padding: 0.5rem 1.5rem;
  background-color: #7c3aed;
  color: white;
  border: none;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background-color 0.2s;

  &:hover {
    background-color: #9333ea;
  }
`;

const LoadingSpinner = styled.span`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
`;

// Tier data
const tiers = [
  {
    name: 'Trial',
    price: 'Free',
    description: 'Get started and explore',
    features: [
      'Find new posts once a day',
      'Unlimited search queries',
      '5 accounts to track',
      'Approve posts before sending',
    ],
    limitations: ['No automatic background discovery', 'No AI-generated replies'],
    cta: 'Current Plan',
    ctaDisabled: true,
    highlight: false,
  },
  {
    name: 'Paid',
    price: '$30',
    period: '/month',
    description: 'Automatic discovery, unlimited tracking',
    features: [
      'Automatic background discovery',
      'Unlimited accounts to track',
      'Unlimited search queries',
      'Approve posts before sending',
    ],
    limitations: ['No automatic reply generation'],
    cta: 'Subscribe',
    ctaDisabled: false,
    highlight: true,
  },
  {
    name: 'Premium',
    price: '$1000',
    period: '/month',
    description: 'Bespoke LLM ghostwriter you can use for everything',
    features: [
      'Auto-generated posts, just edit and approve',
      'Has all the context on your life and work',
      'Custom-trained on your writing',
      'Use it to write anything - blog posts, emails, manifestos',
    ],
    limitations: [],
    cta: 'Get Started',
    ctaDisabled: false,
    highlight: false,
  },
];

export function Pricing() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showContactModal, setShowContactModal] = useState(false);
  const [contactEmail, setContactEmail] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [contactSending, setContactSending] = useState(false);
  const [contactSent, setContactSent] = useState(false);
  const username = localStorage.getItem('username');

  const handleSubscribe = async () => {
    if (!username) {
      navigate('/login');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const { checkout_url } = await api.createCheckoutSession(username);
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start checkout');
      setLoading(false);
    }
  };

  const handleContactSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contactEmail.trim()) return;

    setContactSending(true);
    setError(null);

    try {
      await api.sendPremiumInquiry(contactEmail, contactPhone || undefined, username || undefined);
      setContactSending(false);
      setContactSent(true);
    } catch (err) {
      setContactSending(false);
      setError(err instanceof Error ? err.message : 'Failed to send contact request');
    }
  };

  return (
    <PageContainer>
      <ContentWrapper>
        <Header>
          <Title
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            Organic Growth for Every Kind
          </Title>
          <Subtitle
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            Ghostpost scales with your needs
          </Subtitle>
        </Header>

        {error && <ErrorBanner>{error}</ErrorBanner>}

        <CardsGrid>
          {tiers.map((tier, index) => (
            <CardContainer
              key={tier.name}
              $tierName={tier.name}
              $highlight={tier.highlight}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              whileHover={{
                scale: 1.03,
                y: -8,
                transition: { type: 'spring', stiffness: 300, damping: 20 }
              }}
              transition={{ delay: index * 0.1 }}
            >
              {tier.highlight && (
                <PopularBadge whileHover={{ scale: 1.05 }}>
                  Most Popular
                </PopularBadge>
              )}

              <TierHeader>
                <TierName>{tier.name}</TierName>
                <PriceWrapper
                  whileHover={{ scale: 1.05, originX: 0 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                >
                  <Price $tierName={tier.name}>{tier.price}</Price>
                  {tier.period && <Period>{tier.period}</Period>}
                </PriceWrapper>
                <Description>{tier.description}</Description>
              </TierHeader>

              <FeaturesList>
                {tier.features.map((feature) => (
                  <FeatureItem key={feature}>
                    <CheckIcon>
                      <i className="fas fa-check"></i>
                    </CheckIcon>
                    <FeatureText>{feature}</FeatureText>
                  </FeatureItem>
                ))}
                {tier.limitations.map((limitation) => (
                  <FeatureItem key={limitation}>
                    <MinusIcon>
                      <i className="fas fa-minus"></i>
                    </MinusIcon>
                    <LimitationText>{limitation}</LimitationText>
                  </FeatureItem>
                ))}
              </FeaturesList>

              <CTAButton
                $tierName={tier.name}
                $disabled={tier.ctaDisabled || loading}
                onClick={
                  tier.name === 'Paid'
                    ? handleSubscribe
                    : tier.name === 'Premium'
                    ? () => setShowContactModal(true)
                    : undefined
                }
                disabled={tier.ctaDisabled || loading}
              >
                {loading && tier.name === 'Paid' ? (
                  <LoadingSpinner>
                    <i className="fas fa-spinner fa-spin"></i>
                    Loading...
                  </LoadingSpinner>
                ) : (
                  tier.cta
                )}
              </CTAButton>
            </CardContainer>
          ))}
        </CardsGrid>

        <BackLink>
          <BackButton onClick={() => navigate('/')}>
            <i className="fas fa-arrow-left" style={{ marginRight: '0.5rem' }}></i>
            Back to App
          </BackButton>
        </BackLink>
      </ContentWrapper>

      <AnimatePresence>
        {showContactModal && (
          <ModalOverlay
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowContactModal(false)}
          >
            <ModalContent
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ type: 'spring', duration: 0.3 }}
              onClick={(e) => e.stopPropagation()}
            >
              {contactSent ? (
                <div style={{ textAlign: 'center' }}>
                  <SuccessIcon>
                    <i className="fas fa-check-circle"></i>
                  </SuccessIcon>
                  <ModalTitle>Thanks!</ModalTitle>
                  <ModalSubtitle style={{ marginBottom: '1.5rem' }}>
                    We'll be in touch soon.
                  </ModalSubtitle>
                  <CloseButton
                    onClick={() => {
                      setShowContactModal(false);
                      setContactSent(false);
                      setContactEmail('');
                      setContactPhone('');
                    }}
                  >
                    Close
                  </CloseButton>
                </div>
              ) : (
                <form onSubmit={handleContactSubmit}>
                  <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
                    <ModalTitle>10x your reach with Premium</ModalTitle>
                    <ModalSubtitle>Give us your contact info and we'll reach out!</ModalSubtitle>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
                    <FormGroup>
                      <Label>
                        Email <Required>*</Required>
                      </Label>
                      <Input
                        type="email"
                        value={contactEmail}
                        onChange={(e) => setContactEmail(e.target.value)}
                        placeholder="you@example.com"
                        required
                      />
                    </FormGroup>
                    <FormGroup>
                      <Label>Phone (optional)</Label>
                      <Input
                        type="tel"
                        value={contactPhone}
                        onChange={(e) => setContactPhone(e.target.value)}
                        placeholder="+1 (555) 000-0000"
                      />
                    </FormGroup>
                  </div>

                  <ButtonRow>
                    <CancelButton type="button" onClick={() => setShowContactModal(false)}>
                      Cancel
                    </CancelButton>
                    <SubmitButton
                      type="submit"
                      $disabled={contactSending || !contactEmail.trim()}
                      disabled={contactSending || !contactEmail.trim()}
                    >
                      {contactSending ? (
                        <LoadingSpinner>
                          <i className="fas fa-spinner fa-spin"></i>
                          Sending...
                        </LoadingSpinner>
                      ) : (
                        'Send'
                      )}
                    </SubmitButton>
                  </ButtonRow>
                </form>
              )}
            </ModalContent>
          </ModalOverlay>
        )}
      </AnimatePresence>
    </PageContainer>
  );
}
