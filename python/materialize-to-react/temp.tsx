{/* REPLACEME START */}
<main>
 <div className="navbar-fixed contains-tiny">
  <nav className="tiny" style={{ Filter: brightness(85%) }}>
   <div className="nav-wrapper">
    <Row>
     <Col s={9}>
      <ul className="left">
       <li>
        <Button className="left" href="#" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
         info
        </Button>
       </li>
      </ul>
      <Button className="truncate" href="#" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} target="_blank" waves="light">
       <strong>
        {:environmentwarning}
       </strong>
      </Button>
     </Col>
     <Col s={3}>
      <ul className="right">
       <li>
       </li>
      </ul>
      <Button className="right error-badge" id="commitid" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
       NOT CONNECTED
      </Button>
      <div className="right" id="div_pinglight">
      </div>
     </Col>
    </Row>
   </div>
  </nav>
  <nav>
   <div className="nav-wrapper">
    <Row id="nav-mobile">
     <Col l={6} m={6} s={3}>
      <ul className="left">
       <li>
        <Button className="sidenav-trigger show-on-large" data-target="slide-out" href="#" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
         menu
        </Button>
       </li>
      </ul>
     </Col>
     <Col className="hide-on-large-only" l={6} m={6} s={6} style={{ Padding: 0 10px }}>
      <Row>
       <Col s={1}>
        <ul className="left">
         <li>
          <Button className="left" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
           save
          </Button>
         </li>
         <div id="div_saveuserprefs_progress">
         </div>
        </ul>
       </Col>
       <Col s={1}>
        <ul className="left">
         <li>
          <Button className="left" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
           announcement
          </Button>
         </li>
         <div id="icon_socketactive">
         </div>
        </ul>
       </Col>
       <Col s={10}>
        <ul className="right">
         <li>
          <Button className="left" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
           save
          </Button>
         </li>
         {/* &lt;li&gt;&lt;a id="button_loginuser" class="waves-effect waves-light btn xoxnxauth_hide"&gt;&lt;i class="material-icons left"&gt;cloud&lt;/i&gt;Login&lt;/a&gt;&lt;/li&gt; */}
         <li>
          <Button className="waves-effect waves-light btn onauth_show" id="btn_Notify" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
           chat_bubble
          </Button>
         </li>
         <li>
          <Button className="onauth_show sputniknav" data-href="nestcam.html" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
           camera_outdoor
          </Button>
         </li>
         <li>
          <Button className="onauth_show sputniknav" data-href="mediaview.html" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
           dns
          </Button>
         </li>
         <li>
          <Button className="onauth_show sputniknav" data-href="home.html" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
           home
          </Button>
         </li>
         <li>
          <Button className="" id="btn_userauthentication" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
           login
          </Button>
         </li>
        </ul>
       </Col>
      </Row>
     </Col>
     <Col className="hide-on-med-and-down" l={6} m={6} s={6}>
      <ul className="right">
       <li>
        <Button className="onauth_show" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
         save
        </Button>
       </li>
       {/* &lt;li&gt;&lt;a id="button_loginuser" class="waves-effect waves-light btn onauth_hide"&gt;&lt;i class="material-icons left"&gt;cloud&lt;/i&gt;Login&lt;/a&gt;&lt;/li&gt; */}
       <li>
        <Button className="onauth_show" id="btn_Notify" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
         Notify Me!
        </Button>
       </li>
       <li>
        <Button className="onauth_show sputniknav" data-href="nestcam.html" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
         Live Cameras
        </Button>
       </li>
       <li>
        <Button className="onauth_show sputniknav" data-href="mediaview.html" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
         Media Viewer
        </Button>
       </li>
       <li>
        <Button className="onauth_show sputniknav" data-href="home.html" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
         home
        </Button>
       </li>
       <li>
        <Button className="waves-effect waves-light btn" id="btn_userauthentication" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
         login
        </Button>
       </li>
      </ul>
     </Col>
    </Row>
   </div>
  </nav>
 </div>
 <ul className="sidenav" id="slide-out">
  <li className="logo">
   {/* &lt;img src="/pages/index/_img/sputnik_pagelogo.png"&gt; */}
   <img alt="mainlogo" className="responsive-img center" src="/pages/index/_img/sputnik-large.svg" style={{ MaxHeight: 5rem,  TextAlign: center }}/>
   {/* &lt;object id="front-page-logo" type="image/svg+xml" data="/pages/index/_img/sputnik_pagelogo.png"&gt;Your browser does not support png&lt;/object&gt;&lt;/a&gt;&lt;/li&gt; */}
   <li className="onauth_show no-padding">
    <ul className="collapsible collapsible-accordion" id="collapsible_currentuser">
     <li className="bold">
      <Button className="collapsible-header waves-effect waves-teal" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
       Rohan
       <img alt="" className="circle responsive-img right" src="/pages/index/_img/sputnik-large.svg" style={{ MaxHeight: 3rem }}/>
      </Button>
      <div className="collapsible-body">
       <ul>
        <li>
         <Button className="sputniknav" data-href="admin_user.html" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
          Settings
         </Button>
        </li>
       </ul>
      </div>
     </li>
    </ul>
   </li>
   <li>
    <div className="divider">
    </div>
   </li>
   <li className="onauth_show no-padding">
    <ul className="collapsible collapsible-accordion" id="collapsible_Admin">
     <li className="bold">
      <Button className="collapsible-header waves-effect waves-teal" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
       Admin
      </Button>
      <div className="collapsible-body" style={{ Display: block }}>
       <ul>
        <li>
         <Button className="sputniknav" data-href="admin_system.html" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
          System
         </Button>
        </li>
       </ul>
       <ul>
        <li>
         <Button className="sputniknav" data-href="admin_sputnik.html" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
          Sputnik
         </Button>
        </li>
       </ul>
       <ul>
        <li>
         <Button className="sputniknav" data-href="admin_kodiak.html" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
          Kodiak
         </Button>
        </li>
       </ul>
       <ul>
        <li>
         <Button className="sputniknav" data-href="admin_bugatti.html" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
          Bugatti
         </Button>
        </li>
       </ul>
      </div>
     </li>
    </ul>
   </li>
   {/*/customsidesettings.html*/}
  </li>
 </ul>
 {/* Modal Structure */}
 <div className="modal" id="sputnikmodal_master">
  {/* &lt;div class="row compact"&gt;
        &lt;div class="col s12"&gt; */}
  {/* &lt;div class="row compact"&gt;
            &lt;div class="cols12"&gt; */}
  <nav className="nav">
   <div id="sputnikmodal_header">
   </div>
  </nav>
  <div className="modal-content" id="sputnikmodal_body">
  </div>
  <div className="modal-footer" id="sputnikmodal_footer">
  </div>
  {/* &lt;/div&gt;
      &lt;/div&gt; */}
 </div>
 {/* Modal Structure */}
 <div className="modal" id="modal_JSONViewer">
  <div className="modal-content">
   <h4>
    Modal Header
   </h4>
   <div id="modal_JSONViewer_content">
   </div>
  </div>
  <div className="modal-footer">
   <Button className="modal-close waves-effect waves-green btn-flat" href="#!" node="button" style={{ BackgroundColor: transparent,  BoxShadow: none }} waves="light">
    Close
   </Button>
  </div>
 </div>
 {/*/customnavigation.html*/}
 {/*/custommain.html*/}
</main>
{/*/custombody.html*/}

{/* REPLACEME END */}