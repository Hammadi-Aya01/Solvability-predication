// src/layouts/AppLayout.jsx
import React from 'react';
import { Outlet } from 'react-router-dom';
import { motion } from 'framer-motion';
import Navbar  from '../components/layout/Navbar';
import styles  from './AppLayout.module.css';

const pageVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] } },
  exit:    { opacity: 0, y: -8, transition: { duration: 0.2 } },
};

export default function AppLayout() {
  return (
    <div className={styles.root}>
      <Navbar />
      <motion.main
        className={styles.main}
      >
        <motion.div
          key={window.location.pathname}
          variants={pageVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          className={styles.pageWrapper}
        >
          <Outlet />
        </motion.div>
      </motion.main>
    </div>
  );
}
