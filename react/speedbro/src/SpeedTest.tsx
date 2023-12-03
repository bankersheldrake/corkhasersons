// SpeedTest.tsx
import { Alert, Box, Checkbox, FormControlLabel, Snackbar, Switch, TextField, styled } from '@mui/material';
import React, { useEffect, useState } from 'react';
import Grid from '@mui/material/Unstable_Grid2/Grid2';

const Item = styled('div')({
  textAlign: 'left',
});

interface SpeedInputProps {
  url: string;
  test: boolean;
  label: string;
  sizeInMB?: number;
  error: boolean;
  setUrl: (url: string) => void;
  setTest: (value: boolean) => void;
  setSizeInMB?: (size: number) => void;

}

const SpeedInput: React.FC<SpeedInputProps> = ({ url, test, label, sizeInMB, error, setUrl, setTest, setSizeInMB }) => (
  <Box>
    <Box mb={1}>
      <FormControlLabel 
        control={
          <Switch 
            checked={test} 
            onChange={e => setTest(e.target.checked)} 
            size="small" 
          />
        }
        label={`Test ${label}`}
      />
    </Box>
    {test && (
      <Box>
        <TextField
          label={`${label} URL ${error ? " - Error" : ""}`}
          value={url}
          onChange={e => setUrl(e.target.value)}
          variant="outlined"
          {...(error ? { error: true } : {})}
          helperText={error ? "Incorrect entry." : null}
        />
        {label === 'Upload' && sizeInMB !== undefined && setSizeInMB !== undefined && (
          <Box mt={1}>
            <TextField
              label={`${label} File Size (MB)`}
              value={sizeInMB}
              onChange={e => setSizeInMB(Number(e.target.value))}
              type="number"
              variant="outlined"
            />
          </Box>
        )}
      </Box>
    )}
  </Box>
);





interface SpeedDisplayProps {
  downloadSpeed: number | null;
  uploadSpeed: number | null;
}

const SpeedDisplay: React.FC<SpeedDisplayProps> = ({ downloadSpeed, uploadSpeed }) => (
  <>
    {downloadSpeed && <p>Download Speed: {downloadSpeed.toFixed(2)} Kbps</p>}
    {uploadSpeed && <p>Upload Speed: {uploadSpeed.toFixed(2)} Kbps</p>}
  </>
);
const SpeedTest: React.FC = () => {
  const [downloadSpeed, setDownloadSpeed] = useState<number | null>(null);
  const [uploadSpeed, setUploadSpeed] = useState<number | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string>('');
  const [uploadUrl, setUploadUrl] = useState<string>('');
  const [uploadSizeInMB, setUploadSizeInMB] = useState<number>(5);
  const [testDownload, setTestDownload] = useState<boolean>(true);
  const [testUpload, setTestUpload] = useState<boolean>(true);
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [downloadError, setDownloadError] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<boolean>(false);

  const handleClose = (event: React.SyntheticEvent | Event, reason?: string) => {
    if (reason === 'clickaway') {
      return;
    }
    setOpen(false);
  };

  // Load saved settings from localStorage on component mount
  useEffect(() => {
    const savedTestDownload = JSON.parse(localStorage.getItem('testDownload') || 'false');
    const savedTestUpload = JSON.parse(localStorage.getItem('testUpload') || 'false');
    const savedDownloadUrl = localStorage.getItem('downloadUrl') || '';
    const savedUploadUrl = localStorage.getItem('uploadUrl') || '';
    const savedUploadSizeInMB = JSON.parse(localStorage.getItem('uploadSizeInMB') || '5');

    setTestDownload(savedTestDownload);
    setTestUpload(savedTestUpload);
    setDownloadUrl(savedDownloadUrl);
    setUploadUrl(savedUploadUrl);
    setUploadSizeInMB(savedUploadSizeInMB);
  }, []);

  // Save settings to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('testDownload', JSON.stringify(testDownload));
    localStorage.setItem('testUpload', JSON.stringify(testUpload));
    localStorage.setItem('downloadUrl', downloadUrl);
    localStorage.setItem('uploadUrl', uploadUrl);
    localStorage.setItem('uploadSizeInMB', JSON.stringify(uploadSizeInMB));
  }, [testDownload, testUpload, downloadUrl, uploadUrl, uploadSizeInMB]);
  
  const getSpeedInKbps = (startTime: number, endTime: number, sizeInBytes: number): number => {
    const duration = (endTime - startTime) / 1000; // convert to seconds
    return (sizeInBytes * 8) / (1024 * duration);
  };

  const measureDownloadSpeed = () => {
    const startTime = (new Date()).getTime();
    try {
      fetch(downloadUrl, { mode: 'no-cors' })
        .then(response => {
          // if (!response.ok) {
          //   throw new Error(`HTTP error! status: ${response.status}`);
          // }
          return response.blob();
        })
        .then(blob => {
          const endTime = (new Date()).getTime();
          const speedInKbps = getSpeedInKbps(startTime, endTime, blob.size);
          setDownloadSpeed(speedInKbps);
          setDownloadError(false);  
        })
        .catch(error => {
          setDownloadError(true);  
          if (error instanceof Error) {      
            setMessage(`Error: ${error.message}`);
          }
          setOpen(true);
        });
    } catch (error) {
      setDownloadError(true);  
      if (error instanceof Error) {      
        setMessage(`Error: ${error.message}`);
      }
      setOpen(true);      

    }      
  };

  const measureUploadSpeed = () => {
    const blob = new Blob([(new Array(uploadSizeInMB * 1024 * 1024)).join('a')], { type: 'text/plain' });
    const startTime = (new Date()).getTime();
    try {
      fetch(uploadUrl, { method: 'POST', body: blob })
        .then(response => {
          if (!response.ok) { 
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          const endTime = (new Date()).getTime();
          const speedInKbps = getSpeedInKbps(startTime, endTime, blob.size);
          setUploadSpeed(speedInKbps);
          setUploadError(false);
        })
        .catch(error => {
          if (error instanceof Error) {      
            setMessage(`Error: ${error.message}`);
          }
          setOpen(true);
          setUploadError(true); 
        });
      } catch (error) {
        if (error instanceof Error) {      
          setMessage(`Error: ${error.message}`);
        }
        setOpen(true);        
        setUploadError(true); 

      }
    };

  const startTest = () => {
    if (testDownload) {
      measureDownloadSpeed();
    }
    if (testUpload) {
      measureUploadSpeed();
    }
  };



  return (
    <div>
      <Grid container columns={12} spacing={2}>
        <Grid xs={12} md={6}>
          <Item>
          <SpeedInput 
            url={downloadUrl} 
            test={testDownload} 
            label="Download"
            setUrl={setDownloadUrl} 
            setTest={setTestDownload} 
            error={downloadError} 
          />
          </Item>
        </Grid>
        <Grid>
          <Item >
          <SpeedInput 
              url={uploadUrl} 
              test={testUpload} 
              label="Upload"
              sizeInMB={uploadSizeInMB}
              setUrl={setUploadUrl} 
              setTest={setTestUpload} 
              setSizeInMB={setUploadSizeInMB}
              error={uploadError} 
            />
          </Item>
        </Grid>
      </Grid>
      <button onClick={startTest}>Start Test</button>
      <SpeedDisplay downloadSpeed={downloadSpeed} uploadSpeed={uploadSpeed} />
      <Snackbar open={open} autoHideDuration={6000} onClose={handleClose}>
        <Alert onClose={handleClose} severity="error">
          {message}
        </Alert>
      </Snackbar>     
    </div>
  );
};

export default SpeedTest;