import { useState, useEffect } from 'react';
import { api, type UserSettings, type QueryItem, parseQueryItem } from '../api/client';
import { AnimatedText } from './WordStyles';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import xLottie from '../assets/x.lottie';

interface UserSettingsModalProps {
  isOpen: boolean;
  onClose: (generationHappened?: boolean) => void;
  username: string;
  userInfo: {
    profile_pic_url: string;
    username: string;
    follower_count: number;
  };
  onLogout: () => void;
  isFirstTimeSetup?: boolean;
}

interface BubbleProps {
  children: React.ReactNode;
}

function Bubble({ children }: BubbleProps) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full transition bg-neutral-800">
      {children}
    </div>
  );
}

function SectionTitle({text} : {text: string}) {
  return (
    <label className="block text-white font-mono text-[18px] mb-3">
      {text}
    </label>
  );
}

interface QueryBubbleProps {
  item: QueryItem;
  onSave: (newQuery: string, newSummary: string) => void;
  onRemove: () => void;
}

function QueryBubble({ item, onSave, onRemove }: QueryBubbleProps) {
  const { query, summary } = parseQueryItem(item);
  const [isExpanded, setIsExpanded] = useState(false);
  const [editedQuery, setEditedQuery] = useState(query);
  const [editedSummary, setEditedSummary] = useState(summary);
  const [isDeleteHovered, setIsDeleteHovered] = useState(false);

  // Sync state when item changes
  useEffect(() => {
    const parsed = parseQueryItem(item);
    setEditedQuery(parsed.query);
    setEditedSummary(parsed.summary);
  }, [item]);

  const handleSave = () => {
    if (editedQuery.trim() && (editedQuery !== query || editedSummary !== summary)) {
      onSave(editedQuery.trim(), editedSummary.trim() || summary);
    }
    setIsExpanded(false);
  };

  const twitterSearchUrl = `https://twitter.com/search?q=${encodeURIComponent(query)}&f=live`;

  return (
    <div className={`flex flex-col gap-2 px-3 py-2 rounded-xl transition bg-neutral-800 ${isExpanded ? 'w-full' : ''}`}>
      {/* Collapsed view: summary + icons */}
      <div className="flex items-center gap-2">
        {isExpanded ? (
          <input
            type="text"
            value={editedSummary}
            onChange={(e) => setEditedSummary(e.target.value)}
            placeholder="Summary"
            className="bg-neutral-700 text-white text-sm px-2 py-1 rounded outline-none w-24"
          />
        ) : (
          <span className="text-white text-sm">{summary}</span>
        )}

        {/* Link icon - opens Twitter search */}
        <a
          href={twitterSearchUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-neutral-400 hover:text-sky-400 transition"
          title="View on Twitter"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </a>

        {/* Toggle expand/collapse */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-neutral-400 hover:text-white transition"
          title={isExpanded ? "Collapse" : "Edit query"}
        >
          {isExpanded ? (
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="18 15 12 9 6 15" />
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
          )}
        </button>

        {/* Animated delete button */}
        <button
          onClick={onRemove}
          onMouseEnter={() => setIsDeleteHovered(true)}
          onMouseLeave={() => setIsDeleteHovered(false)}
          className="relative flex items-center justify-center w-6 h-6 rounded-full hover:bg-neutral-700 transition"
          title="Remove query"
        >
          {isDeleteHovered ? (
            <div className="w-5 h-5 flex items-center justify-center">
              <DotLottieReact
                src={xLottie}
                loop
                autoplay
              />
            </div>
          ) : (
            <span className="text-neutral-400 text-sm">x</span>
          )}
        </button>
      </div>

      {/* Expanded view: edit query */}
      {isExpanded && (
        <div className="flex flex-col gap-2">
          <textarea
            value={editedQuery}
            onChange={(e) => setEditedQuery(e.target.value)}
            className="w-full bg-neutral-700 text-white text-sm px-3 py-2 rounded outline-none resize-none min-h-[60px]"
            placeholder="Twitter search query"
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => {
                setEditedQuery(query);
                setEditedSummary(summary);
                setIsExpanded(false);
              }}
              className="text-neutral-400 hover:text-white text-xs px-2 py-1"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="bg-sky-500 hover:bg-sky-600 text-white text-xs px-3 py-1 rounded"
            >
              Save
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


export function UserSettingsModal({ isOpen, onClose, username, userInfo, onLogout, isFirstTimeSetup = false }: UserSettingsModalProps) {
  const [settings, setSettings] = useState<UserSettings>({
    queries: [],
    relevant_accounts: {},
    ideal_num_posts: 30,
    number_of_generations: 1,
    min_impressions_filter: 2000,
    manual_minimum_impressions: null,
    models: [], // Read-only, not editable in settings modal
    intent: '',
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newAccount, setNewAccount] = useState('');
  const [newQuery, setNewQuery] = useState('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [validatingHandle, setValidatingHandle] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const [idealNumPostsInput, setIdealNumPostsInput] = useState<string>('30');
  const [minImpressionsInput, setMinImpressionsInput] = useState<string>('2000');
  const [isManualOverride, setIsManualOverride] = useState(false);
  const [generatingQueries, setGeneratingQueries] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadSettings();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const userSettings = await api.getUserSettings(username);
      setSettings(userSettings);
      setIdealNumPostsInput(userSettings.ideal_num_posts.toString());

      // Determine which value to display and if manual override is active
      const manualValue = userSettings.manual_minimum_impressions;
      const autoValue = userSettings.min_impressions_filter ?? 2000;
      const displayValue = (manualValue !== null && manualValue !== undefined) ? manualValue : autoValue;

      setMinImpressionsInput(displayValue.toString());
      setIsManualOverride(manualValue !== null && manualValue !== undefined);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const showError = (message: string) => {
    setErrorMessage(message);
    setTimeout(() => setErrorMessage(''), 3000);
  };

  const handleAddAccount = async () => {
    if (!newAccount.trim()) return;
    const cleanHandle = newAccount.replace('@', '').trim();

    // Check if already exists
    if (cleanHandle in settings.relevant_accounts) {
      setNewAccount('');
      return;
    }

    // Add with validated: false, then validate
    setValidating(true);
    setValidatingHandle(cleanHandle);
    try {
      // Add with the validation result using the new endpoint
      const addResult = await api.addAccount(username, cleanHandle, true);
      setSettings(addResult.settings);
      setNewAccount('');

      const validation = await api.validateTwitterHandle(username, cleanHandle);

      if (!validation.valid) {
        showError(`Handle @${cleanHandle} is invalid or does not exist.`);
        // Update validation to false using the dedicated endpoint
        const updateResult = await api.updateAccountValidation(username, cleanHandle, false);
        setSettings(updateResult.settings);
      }
    }
    catch (error) {
      console.error('Failed to add account:', error);
      showError((error as Error).message || 'Failed to add account. Please try again.');
    } finally {
      setValidating(false);
      setValidatingHandle(null);
    }
  }


  const handleRemoveAccount = async (account: string) => {
    try {
      const result = await api.removeAccount(username, account);
      setSettings(result.settings);
    } catch (error) {
      console.error('Failed to remove account:', error);
      showError('Failed to remove account. Please try again.');
    }
  };

  const handleAddQuery = () => {
    if (!newQuery.trim()) return;

    // Check if query already exists
    const exists = settings.queries.some(q => {
      const queryStr = Array.isArray(q) ? q[0] : q;
      return queryStr === newQuery.trim();
    });

    if (exists) {
      setNewQuery('');
      return;
    }

    // Add as plain string (user can edit to add summary later)
    setSettings(prev => ({
      ...prev,
      queries: [...prev.queries, newQuery.trim()],
    }));
    setNewQuery('');
  };

  const handleRemoveQuery = async (item: QueryItem) => {
    const queryStr = Array.isArray(item) ? item[0] : item;
    try {
      const result = await api.removeQuery(username, queryStr);
      setSettings(result.settings);
    } catch (error) {
      console.error('Failed to remove query:', error);
      showError('Failed to remove query. Please try again.');
    }
  };

  const handleEditQuery = async (oldItem: QueryItem, newQuery: string, newSummary: string) => {
    const oldQueryStr = Array.isArray(oldItem) ? oldItem[0] : oldItem;

    if (!newQuery.trim()) {
      return;
    }

    try {
      // Remove old query and add new one as [query, summary] tuple
      await api.removeQuery(username, oldQueryStr);
      const newQueries: QueryItem[] = [
        ...settings.queries.filter(q => {
          const qStr = Array.isArray(q) ? q[0] : q;
          return qStr !== oldQueryStr;
        }),
        [newQuery.trim(), newSummary.trim()] as [string, string]
      ];
      const result = await api.updateUserSettings(username, { queries: newQueries });
      setSettings(result.settings);
    } catch (error) {
      console.error('Failed to update query:', error);
      showError('Failed to update query. Please try again.');
    }
  };

  const handleIntentChange = async (newIntent: string) => {
    if (!newIntent.trim()) {
      // If intent is cleared, just update locally
      setSettings(prev => ({ ...prev, intent: newIntent }));
      return;
    }

    try {
      setGeneratingQueries(true);
      // Call API to update intent and generate queries in background
      await api.updateIntent(username, newIntent);

      // Update local state immediately
      setSettings(prev => ({ ...prev, intent: newIntent }));

      // Show notification that queries are being generated
      showError('Generating search queries from your intent in the background...');
      setTimeout(() => setErrorMessage(''), 3000);

      // Reload settings after a delay to get the generated queries
      setTimeout(async () => {
        try {
          const updatedSettings = await api.getUserSettings(username);
          setSettings(updatedSettings);
          setGeneratingQueries(false);
        } catch (error) {
          console.error('Failed to reload settings:', error);
          setGeneratingQueries(false);
        }
      }, 5000); // Wait 5 seconds for background task to complete
    } catch (error) {
      console.error('Failed to update intent:', error);
      showError('Failed to update intent. Please try again.');
      setGeneratingQueries(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);

    try {
      // Fetch current settings from server to check if generation count increased
      const currentSettings = await api.getUserSettings(username);
      setSaving(false);
      const willGenerate = settings.number_of_generations > currentSettings.number_of_generations;

      // If generation will happen, signal parent to show loading overlay BEFORE API call
      if (willGenerate) {
        onClose(true); // This will start the loading overlay and polling
      }

      // Send settings without models (models managed via dedicated endpoint)
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { models, ...settingsToUpdate } = settings;
      await api.updateUserSettings(username, settingsToUpdate);

      // If no generation happened, just close normally
      if (!willGenerate) {
        onClose(false);
      }
      // If generation happened, parent is already handling the loading state
    } catch (error) {
      console.error('Failed to save settings:', error);
      alert('Failed to save settings. Please try again.');
      setSaving(false);
    }
  };

  const handleClose = () => {
    // Prevent closing during first-time setup if no settings configured
    if (isFirstTimeSetup) {
      const hasSettings = settings.queries.length > 0 || Object.keys(settings.relevant_accounts).length > 0;
      if (!hasSettings) {
        showError('Please add at least one account or topic to continue');
        return;
      }
    }
    onClose();
  };


  if (!isOpen) return null;
  

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
      <div className="bg-neutral-900 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header with user info */}
        <div className="sticky top-0 bg-neutral-900 border-b border-neutral-800 p-6">
          <div className="flex justify-end mb-4">
            <button
              onClick={handleClose}
              className="text-neutral-400 hover:text-white transition text-2xl"
            >
              ×
            </button>
          </div>
          <div className="flex flex-col items-center">
            <img
              src={userInfo.profile_pic_url}
              alt={userInfo.username}
              className="w-20 h-20 rounded-full mb-3"
            />
            <h3 className="text-white font-semibold text-[25px]">{userInfo.username}</h3>
            <div className="text-center flex flex-row gap-2">
            <p className="text-neutral-500 text-[18px]">@{username}</p>
            <p className="text-neutral-500 text-[18px]">{userInfo.follower_count.toLocaleString()} followers</p>
            </div>
            {/* Connected X Account */}
            <div className="mt-4 pt-4 border-t border-neutral-800 w-full">
              <div className="flex items-center justify-center gap-3">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" className="text-white">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
                <span className="text-white text-sm">@{username}</span>
                <span className="text-green-400 text-xs px-2 py-0.5 bg-green-900/30 rounded-full">Connected</span>
              </div>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="p-6 text-center text-neutral-400">Loading settings...</div>
        ) : (
          <div className="p-6 space-y-6">
            {/* Welcome banner for first-time setup */}
            {isFirstTimeSetup && (
              <div className="bg-sky-900/30 rounded-lg p-4">
                <h4 className="text-white font-semibold mb-2 flex items-center gap-2">
                  <span>Welcome to GhostPoster!</span>
                </h4>
                <p className="text-neutral-300 text-sm">
                  To get started, please add Twitter accounts and topics you want to engage with.
                  You need at least one account or topic to get started.
                </p>
              </div>
            )}
            {/* Intent */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <SectionTitle text="Your Intent" />
                {generatingQueries && (
                  <span className="text-neutral-400 text-xs flex items-center gap-2">
                    <div className="animate-spin h-3 w-3 border-2 border-sky-500 border-t-transparent rounded-full"></div>
                    Generating queries...
                  </span>
                )}
              </div>
              <textarea
                value={settings.intent || ''}
                onChange={(e) => setSettings(prev => ({ ...prev, intent: e.target.value }))}
                onBlur={(e) => handleIntentChange(e.target.value)}
                placeholder="Describe what you're looking to engage with on Twitter (e.g., 'I'm a VC looking to discuss early-stage startups and talent recruitment')"
                className="w-full bg-neutral-800 text-white px-4 py-3 rounded-[15px] focus:outline-none transition mb-2 min-h-[100px] resize-y"
              />
              <p className="text-neutral-500 text-xs">
                When you update your intent, we'll automatically generate optimized search queries for you.
              </p>
            </div>

            {/* Relevant Accounts */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <SectionTitle text="Relevant Accounts" />
                {validating && (
                  <span className="text-neutral-400 text-xs flex items-center gap-2">
                    <div className="animate-spin h-3 w-3 border-2 border-sky-500 border-t-transparent rounded-full"></div>
                    Validating...
                  </span>
                )}
              </div>
              <input
                type="text"
                value={newAccount}
                onChange={(e) => setNewAccount(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddAccount()}
                placeholder="Add @handle to engage with"
                className="w-full bg-neutral-800 text-white px-4 py-2 rounded-[15px] focus:outline-none transition mb-4"
              />
              {errorMessage && (
                <div className="mb-3 text-red-400 text-sm transition-opacity duration-300">
                  {errorMessage}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                {Object.entries(settings.relevant_accounts).map(([handle, validated]) => {
                  const isValidating = validatingHandle === handle;
                  const isInvalid = validated === false;

                  return (
                    <Bubble key={handle}>
                      {isValidating ? (
                        <AnimatedText
                          text={`@${handle}`}
                          className="text-sky-400 text-sm"
                        />
                      ) : (
                        <span className={`text-sm ${isInvalid ? 'text-neutral-500' : 'text-white'}`}>
                          @{handle}
                        </span>
                      )}
                      {isInvalid && !isValidating && (
                        <span className="text-red-400 text-xs" title="This account is invalid">⚠</span>
                      )}
                      <button
                        onClick={() => handleRemoveAccount(handle)}
                        className="text-neutral-400 hover:text-white transition"
                      >
                        ×
                      </button>
                    </Bubble>
                  );
                })}
              </div>
            </div>

            {/* Topics */}
            <div>
              <SectionTitle text="Search Queries" />
              <input
                type="text"
                value={newQuery}
                onChange={(e) => setNewQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddQuery()}
                placeholder="Add a search query"
                className="w-full bg-neutral-800 text-white px-4 py-2 rounded-[15px] focus:outline-none transition mb-4"
              />
              <div className="flex flex-wrap gap-2">
                {settings.queries.map((item, index) => (
                  <QueryBubble
                    key={index}
                    item={item}
                    onSave={(newQuery, newSummary) => handleEditQuery(item, newQuery, newSummary)}
                    onRemove={() => handleRemoveQuery(item)}
                  />
                ))}
              </div>
            </div>

            {/* Ideal Number of Posts */}
            <div>
              <SectionTitle text="Ideal Number of Posts" />
              <div className="mb-2">
                <span className="text-neutral-400 text-sm">Target number of tweets (system will aim for ±10 of this)</span>
              </div>
              <input
                type="number"
                value={idealNumPostsInput}
                onChange={(e) => setIdealNumPostsInput(e.target.value)}
                onBlur={() => {
                  const parsed = parseInt(idealNumPostsInput);
                  const validated = isNaN(parsed) ? 30 : Math.min(Math.max(parsed, 1), 100);
                  setIdealNumPostsInput(validated.toString());
                  setSettings(prev => ({
                    ...prev,
                    ideal_num_posts: validated,
                  }));
                }}
                min="1"
                max="100"
                className="w-full bg-neutral-800 text-white px-4 py-2 rounded-[15px] focus:outline-none transition"
              />
            </div>

            {/* Min Impressions Filter */}
            <div>
              <SectionTitle text="Minimum Impressions Filter" />
              <div className="mb-2">
                <span className="text-neutral-400 text-sm">
                  {isManualOverride
                    ? "Manual override active - automatic adjustment disabled"
                    : "Filter out tweets from queries/FYP with fewer impressions (0 = no filter)"}
                </span>
              </div>

              {/* Warning when manual override is active */}
              {isManualOverride && (
                <div className="mb-2 px-3 py-2 bg-yellow-900/20 border border-yellow-700/50 rounded-lg">
                  <span className="text-yellow-400 text-sm">
                    ⚠️ Manual override active - this could lead to fewer posts than your ideal number
                  </span>
                </div>
              )}

              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={minImpressionsInput}
                  onChange={(e) => {
                    setMinImpressionsInput(e.target.value);
                    setIsManualOverride(true);  // Mark as manual when user types
                  }}
                  onBlur={() => {
                    // Don't allow empty input - revert to previous value
                    if (minImpressionsInput.trim() === '' || isNaN(parseInt(minImpressionsInput))) {
                      const currentValue = settings.manual_minimum_impressions ?? settings.min_impressions_filter ?? 2000;
                      setMinImpressionsInput(currentValue.toString());
                      return;
                    }

                    const parsed = parseInt(minImpressionsInput);
                    const validated = Math.max(parsed, 0);
                    setMinImpressionsInput(validated.toString());
                    setSettings(prev => ({
                      ...prev,
                      manual_minimum_impressions: validated,
                    }));
                  }}
                  min="0"
                  className={`flex-1 px-4 py-2 rounded-[15px] focus:outline-none transition ${
                    isManualOverride
                      ? 'bg-blue-900/30 border-2 border-blue-500 text-blue-200'
                      : 'bg-neutral-800 text-white'
                  }`}
                />

                {/* X button to clear manual override */}
                {isManualOverride && (
                  <button
                    onClick={() => {
                      setIsManualOverride(false);
                      // Set to the auto-calculated value
                      const autoValue = settings.min_impressions_filter ?? 2000;
                      setMinImpressionsInput(autoValue.toString());
                      setSettings(prev => ({
                        ...prev,
                        manual_minimum_impressions: null,
                      }));
                    }}
                    className="px-3 py-2 bg-red-600 hover:bg-red-700 text-white rounded-[15px] transition"
                    title="Remove manual override"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>

            {/* Number of Generations */}
            <div>
              <SectionTitle text="Reply Generation" />
              <div className="flex items-center gap-4">
                <label className="text-neutral-400 text-sm">Number of replies to generate per tweet:</label>
                <select
                  value={settings.number_of_generations}
                  onChange={(e) => setSettings({...settings, number_of_generations: parseInt(e.target.value)})}
                  className="bg-neutral-800 text-white px-4 py-2 rounded-[15px] focus:outline-none transition"
                >
                  {[1, 2, 3, 4, 5].map(n => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="sticky bottom-0 bg-neutral-900 p-6 flex justify-between items-center">
          <button
            onClick={onLogout}
            className="px-6 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition"
          >
            Logout
          </button>
          <div className="flex gap-3">
            {isFirstTimeSetup ? (
              <button
                onClick={handleSave}
                disabled={saving || loading || (settings.queries.length === 0 && Object.keys(settings.relevant_accounts).length === 0)}
                className="px-6 py-2 rounded-lg bg-sky-500 text-white hover:bg-sky-600 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? 'Saving...' : 'Get Started'}
              </button>
            ) : (
              <>
                <button
                  onClick={handleClose}
                  className="px-6 py-2 rounded-lg bg-neutral-800 text-white hover:bg-neutral-700 transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving || loading || generatingQueries}
                  className="px-6 py-2 rounded-lg bg-sky-500 text-white hover:bg-sky-600 transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? 'Saving...' : generatingQueries ? 'Generating Queries...' : 'Save Changes'}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
