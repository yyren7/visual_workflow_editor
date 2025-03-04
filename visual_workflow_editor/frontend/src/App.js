## frontend/src/App.js
import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import { Container, Typography, AppBar, Toolbar, IconButton, Box } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import FlowEditorWrapper from './components/FlowEditor';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { useTranslation } from 'react-i18next';
import i18n from './i18n'; // Import the i18n configuration
import LanguageSelector from './components/LanguageSelector';

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
  },
});

/**
 * App Component
 *
 * This is the main application component that sets up routing and the overall layout.
 */
const App = () => {
  const { t } = useTranslation();

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Router>
        <AppBar position="static">
          <Toolbar>
            <IconButton
              size="large"
              edge="start"
              color="inherit"
              aria-label="menu"
              sx={{ mr: 2 }}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              {t('Flow Editor')}
            </Typography>
            <LanguageSelector />
          </Toolbar>
        </AppBar>
        <Container maxWidth="xl" sx={{ mt: 2 }}>
          <Routes>
            <Route path="/" element={<Typography variant="body1">{t('Welcome to the Flow Editor!')}</Typography>} />
            <Route path="/flow/:flowId" element={<FlowEditorWrapper />} />
          </Routes>
        </Container>
      </Router>
    </ThemeProvider>
  );
};

export default App;

