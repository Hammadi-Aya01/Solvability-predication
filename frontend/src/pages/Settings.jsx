// src/pages/Settings.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import Spinner from '../components/common/Spinner';
import { authService } from '../services/authService';
import PageHeader from '../components/common/PageHeader';
import Btn        from '../components/common/Btn';
import toast from 'react-hot-toast';
import styles from './Settings.module.css';

export default function Settings() {
  const { user, company, updateUser } = useAuth();
  const [tab, setTab] = useState('profile');
  const [profile, setProfile] = useState({
    nom:    user?.nom    || '',
    prenom: user?.prenom || '',
    email:  user?.email  || '',
  });
  const [passwords, setPasswords] = useState({ current: '', newPass: '', confirm: '' });
  const [savingP,  setSavingP]  = useState(false);
  const [savingPw, setSavingPw] = useState(false);

  // User management states
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newUser, setNewUser] = useState({ fullName: '', email: '', role: 'USER', password: '' });
  const [creatingUser, setCreatingUser] = useState(false);

  const [showPassModal, setShowPassModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [newTempPassword, setNewTempPassword] = useState('');
  const [updatingPass, setUpdatingPass] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoadingUsers(true);
    try {
      const { data } = await authService.getUsers();
      setUsers(data.users || []);
    } catch (err) {
      toast.error('Erreur lors du chargement des utilisateurs');
    } finally {
      setLoadingUsers(false);
    }
  }, []);

  useEffect(() => {
    if (tab === 'users') {
      fetchUsers();
    }
  }, [tab, fetchUsers]);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    if (!newUser.fullName || !newUser.email || !newUser.password) {
      toast.error('Veuillez remplir tous les champs');
      return;
    }
    setCreatingUser(true);
    try {
      await authService.createUser({
        fullName: newUser.fullName,
        email: newUser.email,
        role: newUser.role,
        password: newUser.password
      });
      toast.success('Utilisateur créé avec succès');
      setShowAddModal(false);
      setNewUser({ fullName: '', email: '', role: 'USER', password: '' });
      fetchUsers();
    } catch (err) {
      toast.error(err.response?.data?.error || 'Erreur lors de la création');
    } finally {
      setCreatingUser(false);
    }
  };

  const handleToggleActive = async (userToToggle) => {
    try {
      const updatedActive = !userToToggle.is_active;
      await authService.updateUser(userToToggle.id, { is_active: updatedActive });
      toast.success(`Utilisateur ${updatedActive ? 'activé' : 'désactivé'}`);
      fetchUsers();
    } catch (err) {
      toast.error('Erreur lors de la mise à jour du statut');
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (!newTempPassword) {
      toast.error('Veuillez saisir un mot de passe');
      return;
    }
    setUpdatingPass(true);
    try {
      await authService.updateUser(selectedUser.id, { password: newTempPassword });
      toast.success('Mot de passe mis à jour avec succès');
      setShowPassModal(false);
      setNewTempPassword('');
      setSelectedUser(null);
    } catch (err) {
      toast.error('Erreur lors de la mise à jour du mot de passe');
    } finally {
      setUpdatingPass(false);
    }
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setSavingP(true);
    try {
      const { data } = await authService.updateMe({ nom: profile.nom, prenom: profile.prenom });
      updateUser(data.user);
      toast.success('Profil mis à jour');
    } catch {
      toast.error('Erreur mise à jour');
    } finally {
      setSavingP(false);
    }
  };

  const handleSavePassword = async (e) => {
    e.preventDefault();
    if (!passwords.current) {
      toast.error('Saisissez le mot de passe actuel');
      return;
    }
    if (passwords.newPass !== passwords.confirm) {
      toast.error('Les mots de passe ne correspondent pas');
      return;
    }
    if (passwords.newPass.length < 8) {
      toast.error('Minimum 8 caractères requis');
      return;
    }
    if (!/[A-Z]/.test(passwords.newPass)) {
      toast.error('Au moins une majuscule requise');
      return;
    }
    if (!/\d/.test(passwords.newPass)) {
      toast.error('Au moins un chiffre requis');
      return;
    }
    setSavingPw(true);
    try {
      await authService.changePassword({
        current_password: passwords.current,
        new_password: passwords.newPass,
        confirm_password: passwords.confirm,
      });
      setPasswords({ current: '', newPass: '', confirm: '' });
      toast.success('Mot de passe modifié');
    } catch (err) {
      toast.error(err.response?.data?.error || 'Erreur changement mot de passe');
    } finally {
      setSavingPw(false);
    }
  };

  const initials = `${user?.prenom?.[0] || ''}${user?.nom?.[0] || ''}`.toUpperCase() || '?';

  return (
    <div className={styles.page}>
      <PageHeader title="Paramètres" subtitle="Gérez votre compte et vos préférences" />

      <div className={styles.layout}>
        {/* Side nav */}
        <div className={styles.sideNav}>
          {(user?.role === 'ADMIN'
            ? [['profile','Profil'],['security','Sécurité'],['company','Société'],['users','Utilisateurs']]
            : [['profile','Profil'],['security','Sécurité']]
          ).map(([t, l]) => (
            <button
              key={t}
              className={`${styles.sideBtn} ${tab === t ? styles.sideBtnActive : ''}`}
              onClick={() => setTab(t)}
            >
              {l}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className={styles.content}>

          {/* ── Profile ── */}
          {tab === 'profile' && (
            <motion.div className={styles.card} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <h2 className={styles.cardTitle}>Mon Profil</h2>

              <div className={styles.avatarSection}>
                <div className={styles.avatarBig}>{initials}</div>
                <div>
                  <div className={styles.avatarName}>{user?.prenom} {user?.nom}</div>
                  <div className={styles.avatarEmail}>{user?.email}</div>
                  <div className={styles.avatarRole}>{user?.role}</div>
                </div>
              </div>

              <form onSubmit={handleSaveProfile} className={styles.form}>
                <div className={styles.formRow}>
                  <div className={styles.field}>
                    <label className={styles.label}>Prénom</label>
                    <input
                      className="input-base"
                      value={profile.prenom}
                      onChange={e => setProfile(p => ({ ...p, prenom: e.target.value }))}
                      placeholder="Votre prénom"
                    />
                  </div>
                  <div className={styles.field}>
                    <label className={styles.label}>Nom</label>
                    <input
                      className="input-base"
                      value={profile.nom}
                      onChange={e => setProfile(p => ({ ...p, nom: e.target.value }))}
                      placeholder="Votre nom"
                    />
                  </div>
                </div>
                <div className={styles.field}>
                  <label className={styles.label}>Email</label>
                  <input className="input-base" value={profile.email} disabled style={{ opacity: 0.6 }} />
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>L'email ne peut pas être modifié.</span>
                </div>
                <div className={styles.field}>
                  <label className={styles.label}>Rôle</label>
                  <input className="input-base" value={user?.role || ''} disabled style={{ opacity: 0.6 }} />
                </div>
                <Btn type="submit" variant="primary" loading={savingP}>
                  Enregistrer le profil
                </Btn>
              </form>
            </motion.div>
          )}

          {/* ── Security ── */}
          {tab === 'security' && (
            <motion.div className={styles.card} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <h2 className={styles.cardTitle}>Sécurité</h2>
              <p className={styles.helpText}>Modifiez le mot de passe de votre compte utilisateur.</p>
              <form onSubmit={handleSavePassword} className={styles.form}>
                <div className={styles.field}>
                  <label className={styles.label}>Mot de passe actuel</label>
                  <input
                    type="password"
                    className="input-base"
                    value={passwords.current}
                    onChange={e => setPasswords(p => ({ ...p, current: e.target.value }))}
                    placeholder="••••••••"
                    autoComplete="current-password"
                    required
                  />
                </div>
                <div className={styles.field}>
                  <label className={styles.label}>Nouveau mot de passe</label>
                  <input
                    type="password"
                    className="input-base"
                    value={passwords.newPass}
                    onChange={e => setPasswords(p => ({ ...p, newPass: e.target.value }))}
                    placeholder="••••••••"
                    autoComplete="new-password"
                    required
                  />
                </div>
                <div className={styles.field}>
                  <label className={styles.label}>Confirmer le mot de passe</label>
                  <input
                    type="password"
                    className="input-base"
                    value={passwords.confirm}
                    onChange={e => setPasswords(p => ({ ...p, confirm: e.target.value }))}
                    placeholder="••••••••"
                    autoComplete="new-password"
                    required
                  />
                </div>

                {passwords.newPass && (
                  <div className={styles.pwStrength}>
                    {[
                      { label: '8+ caractères', ok: passwords.newPass.length >= 8 },
                      { label: 'Majuscule',      ok: /[A-Z]/.test(passwords.newPass) },
                      { label: 'Chiffre',        ok: /\d/.test(passwords.newPass) },
                    ].map(r => (
                      <span key={r.label} style={{ color: r.ok ? 'var(--green)' : 'var(--text-muted)', fontSize: 12 }}>
                        {r.ok ? '✓' : '○'} {r.label}
                      </span>
                    ))}
                  </div>
                )}

                <Btn type="submit" variant="primary" loading={savingPw}>
                  Modifier le mot de passe
                </Btn>
              </form>

              <div className={styles.divider} />
              <div className={styles.dangerZone}>
                <h3 className={styles.dangerTitle}>Session active</h3>
                <div className={styles.sessionItem}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>Session actuelle</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Navigateur — Tunis</div>
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--green)', background: 'var(--green-dim)', padding: '2px 8px', borderRadius: 99 }}>
                    Active
                  </span>
                </div>
              </div>
            </motion.div>
          )}

          {/* ── Company ── */}
          {tab === 'company' && (
            <motion.div className={styles.card} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <h2 className={styles.cardTitle}>Informations Société</h2>
              <div className={styles.companyInfo}>
                {[
                  ['Nom',    company?.name],
                  ['Email',  company?.email],
                  ['Statut', company?.is_active ? 'Actif' : 'Inactif'],
                ].map(([k, v]) => (
                  <div key={k} className={styles.infoRow}>
                    <span className={styles.infoKey}>{k}</span>
                    <span className={styles.infoVal}>{v || '—'}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* ── Users ── */}
          {tab === 'users' && (
            <motion.div className={styles.card} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <div className={styles.cardHeader}>
                <h2 className={styles.cardTitle} style={{ marginBottom: 0 }}>Gestion des Utilisateurs</h2>
                <Btn variant="primary" onClick={() => setShowAddModal(true)}>
                  Ajouter un utilisateur
                </Btn>
              </div>

              {loadingUsers ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
                  <Spinner size={24} />
                </div>
              ) : users.length === 0 ? (
                <div className={styles.emptyState}>Aucun utilisateur trouvé</div>
              ) : (
                <div className={styles.tableWrapper}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Nom complet</th>
                        <th>Email</th>
                        <th>Rôle</th>
                        <th>Statut</th>
                        <th>Dernière connexion</th>
                        <th style={{ textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map(u => {
                        const uInitials = `${u.prenom?.[0] || ''}${u.nom?.[0] || ''}`.toUpperCase() || '?';
                        return (
                          <tr key={u.id}>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                <div className={styles.avatarSmall}>{uInitials}</div>
                                <span>{u.prenom} {u.nom}</span>
                              </div>
                            </td>
                            <td>{u.email}</td>
                            <td>
                              <span className={`${styles.roleBadge} ${u.role === 'ADMIN' ? styles.roleAdmin : styles.roleUser}`}>
                                {u.role === 'ADMIN' ? 'Administrateur' : 'Agent'}
                              </span>
                            </td>
                            <td>
                              <span className={`${styles.statusBadge} ${u.is_active ? styles.statusActive : styles.statusInactive}`}>
                                {u.is_active ? 'Actif' : 'Inactif'}
                              </span>
                            </td>
                            <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                              {u.last_login ? new Date(u.last_login).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : 'Jamais'}
                            </td>
                            <td>
                              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                                <button 
                                  className={styles.actionBtn} 
                                  onClick={() => handleToggleActive(u)}
                                >
                                  {u.is_active ? 'Désactiver' : 'Activer'}
                                </button>
                                <button 
                                  className={styles.actionBtn} 
                                  onClick={() => { setSelectedUser(u); setShowPassModal(true); }}
                                >
                                  Mot de passe
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </motion.div>
          )}

        </div>
      </div>

      {/* ── Add User Modal ── */}
      <AnimatePresence>
        {showAddModal && (
          <div className={styles.modalOverlay} onClick={() => setShowAddModal(false)}>
            <motion.div 
              className={styles.modalCard}
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              onClick={e => e.stopPropagation()}
            >
              <h3 className={styles.modalTitle}>Ajouter un utilisateur</h3>
              <form onSubmit={handleCreateUser} className={styles.form}>
                <div className={styles.field}>
                  <label className={styles.label}>Nom complet</label>
                  <input
                    className="input-base"
                    placeholder="Jean Dupont"
                    value={newUser.fullName}
                    onChange={e => setNewUser(prev => ({ ...prev, fullName: e.target.value }))}
                    required
                  />
                </div>
                <div className={styles.field}>
                  <label className={styles.label}>Adresse e-mail</label>
                  <input
                    type="email"
                    className="input-base"
                    placeholder="agent@entreprise.com"
                    value={newUser.email}
                    onChange={e => setNewUser(prev => ({ ...prev, email: e.target.value }))}
                    required
                  />
                </div>
                <div className={styles.field}>
                  <label className={styles.label}>Rôle</label>
                  <select
                    className="input-base"
                    value={newUser.role}
                    onChange={e => setNewUser(prev => ({ ...prev, role: e.target.value }))}
                    style={{ background: 'var(--bg-elevated)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: '10px 12px' }}
                  >
                    <option value="USER">Agent</option>
                    <option value="ADMIN">Administrateur</option>
                  </select>
                </div>
                <div className={styles.field}>
                  <label className={styles.label}>Mot de passe temporaire</label>
                  <input
                    type="password"
                    className="input-base"
                    placeholder="••••••••"
                    value={newUser.password}
                    onChange={e => setNewUser(prev => ({ ...prev, password: e.target.value }))}
                    required
                  />
                </div>
                <div className={styles.modalActions}>
                  <Btn type="button" variant="secondary" onClick={() => setShowAddModal(false)}>
                    Annuler
                  </Btn>
                  <Btn type="submit" variant="primary" loading={creatingUser}>
                    Créer l'utilisateur
                  </Btn>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── Reset Password Modal ── */}
      <AnimatePresence>
        {showPassModal && (
          <div className={styles.modalOverlay} onClick={() => { setShowPassModal(false); setSelectedUser(null); }}>
            <motion.div 
              className={styles.modalCard}
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              onClick={e => e.stopPropagation()}
            >
              <h3 className={styles.modalTitle}>Modifier le mot de passe</h3>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
                Définir un nouveau mot de passe temporaire pour <strong>{selectedUser?.prenom} {selectedUser?.nom}</strong>.
              </p>
              <form onSubmit={handleResetPassword} className={styles.form}>
                <div className={styles.field}>
                  <label className={styles.label}>Nouveau mot de passe temporaire</label>
                  <input
                    type="password"
                    className="input-base"
                    placeholder="••••••••"
                    value={newTempPassword}
                    onChange={e => setNewTempPassword(e.target.value)}
                    required
                  />
                </div>
                <div className={styles.modalActions}>
                  <Btn type="button" variant="secondary" onClick={() => { setShowPassModal(false); setSelectedUser(null); }}>
                    Annuler
                  </Btn>
                  <Btn type="submit" variant="primary" loading={updatingPass}>
                    Enregistrer
                  </Btn>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
}
