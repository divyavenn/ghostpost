import { useState, useEffect } from 'react';
import { api, type UserSettings } from '../api/client';
import { AnimatedText } from './AnimatedText';

interface UserSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  username: string;
  userInfo: {
    profile_pic_url: string;
    username: string;
    follower_count: number;
  };
  onLogout: () => void;
}

interface EditableTextProps {
  text: string;
  onSave: (newText: string) => void;
}

function EditableText({ text, onSave }: EditableTextProps) {
  const [value, setValue] = useState(text);

  const handleSave = () => {
    if (value.trim() && value !== text) {
      onSave(value);
    }
  };

  return (
    <input
      type="text"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') handleSave();
        else if (e.key === 'Escape') setValue(text);
      }}
      onBlur={handleSave}
      style={{ width: `${Math.max(value.length * 6.8, 60)}px` }}
      className="bg-transparent text-white text-sm outline-none cursor-text"
    />
  );
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


export function UserSettingsModal({ isOpen, onClose, username, userInfo, onLogout }: UserSettingsModalProps) {
  const [settings, setSettings] = useState<UserSettings>({
    queries: [],
    relevant_accounts: {},
    max_tweets_retrieve: 30,
  });
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newAccount, setNewAccount] = useState('');
  const [newQuery, setNewQuery] = useState('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [validatingHandle, setValidatingHandle] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadSettings();
    }
  }, [isOpen, username]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const userSettings = await api.getUserSettings(username);
      setSettings(userSettings);
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
    if (settings.queries.includes(newQuery.trim())) {
      setNewQuery('');
      return;
    }

    setSettings(prev => ({
      ...prev,
      queries: [...prev.queries, newQuery.trim()],
    }));
    setNewQuery('');
  };

  const handleRemoveQuery = async (query: string) => {
    try {
      const result = await api.removeQuery(username, query);
      setSettings(result.settings);
    } catch (error) {
      console.error('Failed to remove query:', error);
      showError('Failed to remove query. Please try again.');
    }
  };

  const handleEditQuery = async (oldQuery: string, newQuery: string) => {
    if (!newQuery.trim() || newQuery === oldQuery) {
      return;
    }

    try {
      // Remove old query and add new one
      await api.removeQuery(username, oldQuery);
      const newQueries = [...settings.queries.filter(q => q !== oldQuery), newQuery.trim()];
      const result = await api.updateUserSettings(username, { queries: newQueries });
      setSettings(result.settings);
    } catch (error) {
      console.error('Failed to update query:', error);
      showError('Failed to update query. Please try again.');
    }
  };


  const handleSave = async () => {
    setSaving(true);
    try {
      await api.updateUserSettings(username, settings);
      onClose();
    } catch (error) {
      console.error('Failed to save settings:', error);
      alert('Failed to save settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };


  if (!isOpen) return null;
  

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
      <div className="bg-neutral-900 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header with user info */}
        <div className="sticky top-0 bg-neutral-900 border-b border-neutral-800 p-6">
          <div className="flex justify-end mb-4">
            <button
              onClick={onClose}
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
          </div>
        </div>

        {loading ? (
          <div className="p-6 text-center text-neutral-400">Loading settings...</div>
        ) : (
          <div className="p-6 space-y-6">
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
              <SectionTitle text="Topics & Keywords" />
              <input
                type="text"
                value={newQuery}
                onChange={(e) => setNewQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddQuery()}
                placeholder="Add topics or keywords to engage with"
                className="w-full bg-neutral-800 text-white px-4 py-2 rounded-[15px] focus:outline-none transition mb-4"
              />
              <div className="flex flex-wrap gap-2">
                {settings.queries.map((query, index) => (
                  <Bubble key={index}>
                    <EditableText
                      text={query}
                      onSave={(newText) => handleEditQuery(query, newText)}
                    />
                    <button
                      onClick={() => handleRemoveQuery(query)}
                      className="text-neutral-400 hover:text-white transition"
                    >
                      ×
                    </button>
                  </Bubble>
                ))}
              </div>
            </div>

            {/* Max Tweets */}
            <div>
              <SectionTitle text="Max Tweets to Retrieve" />
              <input
                type="number"
                value={settings.max_tweets_retrieve}
                onChange={(e) => setSettings(prev => ({
                  ...prev,
                  max_tweets_retrieve: parseInt(e.target.value) || 30,
                }))}
                min="1"
                max="100"
                className="w-full bg-neutral-800 text-white px-4 py-2 rounded-[15px] focus:outline-none transition"
              />
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="sticky bottom-0 bg-neutral-900 border-t border-neutral-800 p-6 flex justify-between items-center">
          <button
            onClick={onLogout}
            className="px-6 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition"
          >
            Logout
          </button>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-6 py-2 rounded-lg bg-neutral-800 text-white hover:bg-neutral-700 transition"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || loading}
              className="px-6 py-2 rounded-lg bg-sky-500 text-white hover:bg-sky-600 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
